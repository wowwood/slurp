import json
import os
import pathlib
import queue
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from glob import glob
from typing import Generator

from slurp import FetcherMisconfiguredError
from slurp.fetchers.exceptions import AmbiguousQueryError, NoUpstreamMetadataError
from slurp.fetchers.types import (
    Fetcher,
    FetcherMediaMetadataAvailable,
    FetcherProgressReport,
    FetcherUpdateEvent,
    Format,
    MediaMetadata,
)


class BBCiPlayerFetcher(Fetcher):
    """BBCiPlayerFetcher is a fetcher that uses an available get_iplayer binary to download media from the BBC."""

    name = "get_iplayer"

    _bin_name = "get_iplayer"

    def __backend_available(self) -> bool:
        """__backend_available returns True if we can call get_iplayer. Exception thrown otherwise."""
        assert self._bin_name is not ""
        try:
            proc = subprocess.run(
                [self._bin_name, "-V"],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            raise FetcherMisconfiguredError(f"Cannot call get_iplayer binary: {e}")
        if proc.returncode != 0:
            raise FetcherMisconfiguredError(
                f"Cannot call get_iplayer binary: {self._bin_name} returned {proc.returncode}"
            )
        return True

    @property
    def ready(self) -> bool:
        """We're Ready if the get_iplayer binary is available."""
        try:
            return self.__backend_available()
        except FetcherMisconfiguredError:
            return False

    # We're quite a specific fetcher, so relatively high priority.
    priority = 10

    service_names = ["BBC iPlayer"]
    service_urls = ["bbc.co.uk/iplayer", "bbc.co.uk/sounds"]

    @staticmethod
    def _log_emit(log: str) -> FetcherProgressReport:
        """_log_emit produces a FetcherProgressReport with the appropriate level for the given get_iplayer log line."""
        if log.startswith("ERROR: "):
            return FetcherProgressReport(
                typ="log", level="error", message=log.replace("ERROR: ", "")
            )
        elif log.startswith("WARNING: "):
            return FetcherProgressReport(
                typ="log", level="warning", message=log.replace("WARNING: ", "")
            )
        elif log.startswith("INFO: "):
            return FetcherProgressReport(
                typ="log", level="info", message=log.replace("INFO: ", "")
            )
        else:
            return FetcherProgressReport(
                typ="log", level="debug", message=log.replace("DEBUG: ", "")
            )

    def _get_metadata(self, url: str) -> MediaMetadata:
        """_get_metadata returns MediaMetadata for the given url."""

        # get_iplayer spews metadata in a very annoying way (to allow for listing).
        # To solve this, we call the binary and get it to dump metadata to a temporary directory,
        # then attempt to find that - loading it in if we succeed.
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = subprocess.run(
                [
                    "get_iplayer",
                    url,
                    "--metadata-only",
                    "--metadata=json",
                    "--overwrite",
                    f"--output={tmpdir}",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            assert proc.returncode == 0, (
                f"get_iplayer failed with code {proc.returncode}"
            )

            # Find the metadata file.
            meta_files = os.listdir(tmpdir)
            if len(meta_files) == 0:
                raise NoUpstreamMetadataError(
                    "get_iplayer could not find any metadata for the given URL"
                )
            if len(meta_files) != 1:
                raise AmbiguousQueryError(
                    f"get_iplayer found {len(meta_files)} matching targets for the given URL - please refine."
                )

            meta_file = meta_files[0]

            # Load its JSON.
            meta = json.loads(open(f"{tmpdir}/{meta_file}").read())

            assert "brand" in meta, "brand key not in returned metadata file"
            if meta["brand"] == "get_iplayer":
                # This seems to happen if get_iplayer had some kind of issue retrieving the metadata file.
                raise NoUpstreamMetadataError(
                    "get_iplayer returned a result, but the response seems to indicate this media does not exist."
                )

            data = MediaMetadata(url)

            data.name = meta.get("title")
            data.author = meta.get("channel")
            data.author_url = meta.get("web")
            data.ts_upload = (
                datetime.fromisoformat(meta.get("firstbcast"))
                if meta.get("firstbcast")
                else None
            )
            data.duration = meta.get("duration")

            data.thumbnail_url = meta.get("thumbnail")

            data.format = meta.get("type")
        return data

    def _get_media(
        self,
        q: queue.Queue[FetcherUpdateEvent],
        url: str,
        fmt: Format,
        directory: str,
        filename: str,
    ):
        """
        Commence a download from BBC iPlayer.
        Consider threading this to allow for asynchronous downloads.
        """
        try:
            # We support early metadata - send that if it's available.
            metadata = self._get_metadata(url)
            if metadata.name != "":
                event = FetcherMediaMetadataAvailable(metadata=metadata)
                q.put(event)

            if fmt != Format.VIDEO_AUDIO:
                q.put(
                    FetcherProgressReport(
                        typ="log",
                        level="warning",
                        message="get_iplayer does not support the Format function - you will receive media in the same format as the origin.",
                    )
                )

            proc = subprocess.Popen(
                [
                    "get_iplayer",
                    "-g",
                    url,
                    "--force",
                    "--overwrite",
                    f"--file-prefix={filename}",
                    "--radio-quality=high",
                    "--tv-quality=hd",
                    f"--output={directory}/temp",
                ],
                stdout=subprocess.PIPE,
                bufsize=1,
                text=True,
            )
            for o in proc.stdout:
                q.put(self._log_emit(o))

            # Wait for process to finish returning
            proc.poll()
            assert proc.returncode == 0, (
                f"get_iplayer failed with code {proc.returncode}"
            )

            # Find the downloaded file.
            files = glob(f"{directory}/temp/{filename}.*")
            assert len(files) == 1, (
                f"unexpected number of files in bagging area: {len(files)}"
            )
            target = files[0]
            target_extension = pathlib.Path(target).suffix
            destination = f"{directory}/{filename}{target_extension}"

            # Once writing is finished, move to final location
            # Done using an OS move command so that the OS filesystem properly locks / unlocks the target
            # (which means any processing up the pipe from us doesn't start trying to read the file prematurely)
            q.put(
                FetcherProgressReport(
                    typ="log",
                    level="info",
                    message=f"Moving file from temporary directory to {destination}",
                )
            )

            try:
                shutil.move(target, destination)
            except Exception as e:
                q.put(
                    FetcherProgressReport(
                        typ="finish",
                        level="error",
                        status=1,
                        message=f"exception occurred moving downloaded file: {e}",
                    )
                )
                q.shutdown()
                return

            q.put(
                FetcherProgressReport(
                    typ="finish",
                    level="info",
                    status=0,
                    message="Fetcher complete",
                )
            )
        except Exception as e:
            q.put(
                FetcherProgressReport(
                    typ="finish",
                    level="error",
                    status=1,
                    message=f"Fetcher Exception: {e}",
                )
            )
        finally:
            # signal end of data
            q.shutdown()

    def fetch(
        self,
        url: str,
        fmt: Format,
        directory: str,
        filename: str,
    ) -> Generator[FetcherUpdateEvent]:
        """get_media downloads the media at the given params in the foreground, returning log information by means of a Generator."""
        q: queue.Queue[FetcherUpdateEvent] = queue.Queue()

        # We need to run the download on a thread so we can continue to execute our client response
        thread = threading.Thread(
            target=self._get_media(q, url, fmt, directory, filename), daemon=True
        )
        thread.start()

        while True:
            try:
                # Reasonably sane timeout, just to stop us endlessly spinning.
                event: FetcherUpdateEvent = q.get(timeout=300)
            except queue.ShutDown:
                # End of data.
                break
            match event:
                case FetcherProgressReport() as i:
                    if i.typ == "finish":
                        yield i
                        # Break the generator.
                        break
                    yield i
                case FetcherMediaMetadataAvailable() as i:
                    yield i
