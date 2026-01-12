import os
import queue
import shutil
import threading
from typing import Generator

import httpx
from markupsafe import escape
from slurp.fetchers.types import Fetcher, MediaMetadata, Format


class CobaltFetcher(Fetcher):
    """ CobaltFetcher is a fetcher that uses a given Cobalt instance to download media."""
    name = "cobalt"

    url = ""
    key: str | None = None

    def __init__(self, url: str, key: str=None):
        self.url = url
        self.key = key if key != '' else None

    @property
    def service_names(self) -> list[str]:
        """ service_names returns a list of services that the Cobalt instance reports as being supported. """
        response_data = httpx.get(self.url, headers=self._headers()).raise_for_status().json()
        assert "cobalt" in response_data
        return [(lambda x: x.capitalize())(svc) for svc in response_data['cobalt'].get('services', [])]

    @property
    def service_urls(self) -> list[str] | None:
        """
        service_urls returns the supported services that we can query for data.
        Cobalt is a special instance: we attempt to download anything that is otherwise unsupported by another module.
        """
        # Special return: we support anything that the backend supports.
        return None

    def _headers(self) -> dict[str, str]:
        """ _headers builds a set of JSON acceptance headers for an API request to a Cobalt instance. """
        cfg = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "wowwood/slurp",
        }
        if self.key is not None:
            cfg["Authorization"] = f"Api-Key {self.key}"

        return cfg

    @classmethod
    def _req_data(cls, url: str, fmt: Format) -> dict:
        """ _req_data builds the request parameters for a media download request to a Cobalt instance.
        """
        cfg = {
            "url": url,
            "filenameStyle": "basic",
        }

        match fmt:
            case fmt.VIDEO_AUDIO:
                cfg["downloadMode"] = "auto"
                cfg["videoQuality"] = "max"
                cfg["audioBitrate"] = "320"
                cfg["audioFormat"] = "best"
            case fmt.AUDIO_ONLY:
                cfg["downloadMode"] = "audio"
                cfg["audioBitrate"] = "320"
                cfg["audioFormat"] = "best"
            case fmt.VIDEO_ONLY:
                cfg["downloadMode"] = "mute"
                cfg["videoQuality"] = "max"

        return cfg

    def get_metadata(self, url: str, fmt: Format = Format.VIDEO_AUDIO) -> MediaMetadata | None:
        """ Cobalt can't presently return metadata without just downloading the file. """
        return None

    def _get_media(self, q: queue.Queue, url: str, fmt: Format, directory: str, filename: str):
        """
        Commence a download.
        """

        # Scope response_data appropriately
        response_data: dict = {}

        try:
            response = httpx.post("http://localhost:9000/", headers=self._headers(), json=self._req_data(url, fmt))
            response_data = response.json()
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response_data.get("error") is not None:
                q.put(("error", f"cobalt backend returned status {e.response.status_code}: {response_data['error'].get('code', 'Unknown Error')}"))
            else:
                q.put(("error", f"cobalt backend returned status {e.response.status_code}: {e}"))
            q.put(("finish", 1))
            q.put(None)
            return
        except Exception as e:
            q.put(("error", f"cobalt request exception: {e}"))
            q.put(("finish", 1))
            q.put(None)
            return


        # Assurance that we've got the expected response type
        try:
            assert "status" in response_data
            assert "url" in response_data
            assert "filename" in response_data
        except AssertionError as e:
            q.put(("error", f"unexpected cobalt response: {e}"))

        match response_data.get("status", None):
            case "tunnel":
                # Tunneled response
                q.put(("info", f"Received Tunnel - fetching {response_data.get("filename")} from remux..."))
            case "redirect":
                # Redirection to origin download
                q.put(("info", f"Received Redirect - fetching {response_data.get("filename")} from origin..."))

        # Grab to target

        # Discover file extension
        _, extension = os.path.splitext(response_data.get('filename'))
        # Open a temporary file
        try:
            target = f"{directory}/temp/{filename}.tmp"
            # make sure the temporary download directory exists
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, mode='wb') as f:
                with httpx.stream("GET", response_data.get("url")) as r:
                    num_bytes_downloaded = r.num_bytes_downloaded
                    if r.headers.get("content-length") is not None:
                        q.put(("info", f"Downloading media: size {r.headers.get('content-length')}B"))
                    elif r.headers.get("estimated-content-length") is not None:
                        q.put(("info", f"Downloading media: APPROXIMATE size {r.headers.get('estimated-content-length')}B"))
                    else:
                        q.put(("info", f"Downloading file..."))

                    for data in r.iter_bytes():
                        f.write(data)
                        num_bytes_downloaded = r.num_bytes_downloaded

                    q.put(("debug", f"cobalt download complete - size {num_bytes_downloaded}B"))
                    if num_bytes_downloaded == 0:
                        raise Exception("no bytes received")
        except Exception as e:
            q.put(("error", f"cobalt download exception: {e}"))
            q.put(("finish", 1))
            q.put(None)
            return

        # Once writing is finished, move to final location
        # Done using an OS move command so that the OS filesystem properly locks / unlocks the target
        # (which means any processing up the pipe from us doesn't start trying to read the file prematurely)
        q.put(("info", f"Moving file from temporary directory to {directory}/{filename}{extension}"))
        try:
            shutil.move(target, f'{directory}/{filename}{extension}')
        except Exception as e:
            q.put(("error", f"error moving downloaded file: {e}"))
            q.put(("finish", 1))
            q.put(None)
            return

        # signals end of stream
        q.put(("finish", 0))
        q.put(None)

    def get_media(self, url: str, fmt: Format, directory: str, filename: str) -> Generator[str]:
        """ get_media downloads the media at the given params in the foreground, returning log information by means of a Generator. """
        q = queue.Queue()

        # Start background thread to run the pybalt download
        t = threading.Thread(target=self._get_media(q, url, fmt, directory, filename), daemon=True)
        t.start()

        # We need to run the download on a thread so we can continue to execute our client response

        while True:
            item = q.get()
            if item is None:
                break
            typ, payload = item
            line_fmt = ""
            match typ:
                case "info":
                    line_fmt = "color: blue"
                case "warn":
                    line_fmt = "color: orange"
                case "error":
                    line_fmt = "color: red"
                case "finish":
                    if payload != 0:
                        yield f"<span style='color:red'>❌ Slurp failed!</span> Please check the logs above."
                    else:
                        yield f"<span style='color:green'>🥤 Slurp successful</span>"
                    continue
            yield f"<span style='{line_fmt}'>{typ}</span>: {escape(payload)}"