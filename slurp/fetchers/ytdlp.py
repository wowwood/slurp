import queue
import threading
from datetime import datetime, timezone
from typing import Generator

from yt_dlp import YoutubeDL

from slurp.fetchers.types import (
    Fetcher,
    FetcherMediaMetadataAvailable,
    FetcherProgressReport,
    FetcherUpdateEvent,
    Format,
    MediaMetadata,
)


class YTDLPFetcher(Fetcher):
    """YTDLPFetcher is a fetcher that uses the YT-DLP library to download media exclusively from YouTube."""

    name = "yt-dlp"

    # YT-DLP is always ready.
    ready = True

    # We're quite a specific fetcher, so relatively high priority.
    priority = 10

    service_names = ["Youtube"]
    service_urls = ["youtube.com", "youtu.be"]

    class _Queuelogger:
        """queueLogger provides a yt-dlp compatible logging interface that emits exclusively to a queue."""

        def __init__(self, q: queue.Queue[FetcherUpdateEvent]):
            self.q = q

        def debug(self, msg):
            # As recommended by library documentation
            if msg.startswith("[debug] "):
                self.q.put(FetcherProgressReport(typ="log", level="debug", message=msg))
            else:
                self.info(msg)

        def info(self, msg):
            self.q.put(FetcherProgressReport(typ="log", level="info", message=msg))

        def warning(self, msg):
            self.q.put(FetcherProgressReport(typ="log", level="warning", message=msg))

        def error(self, msg):
            self.q.put(FetcherProgressReport(typ="log", level="error", message=msg))

    @classmethod
    def _format_config(cls, fmt: Format) -> dict:
        """_format_config returns YT-DLP configuration to be used when downloading media in the given format.
        :param fmt: The desired media format.
        :return: A YT-DLP configuration parameters dictionary.
        """
        match fmt:
            case fmt.VIDEO_AUDIO:
                return {
                    "format": "bestvideo*+bestaudio/best",
                }
                # force codec to h264 m4a/mp4
                # fails if this format isn't available, fix later
                # return ['-f', 'bv*[vcodec^=avc]+ba[ext=m4a]/b[ext=mp4]/b']
            case fmt.AUDIO_ONLY:
                return {
                    "format": "m4a/bestaudio/best",
                    "postprocessors": [
                        {  # Extract audio using ffmpeg
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "m4a",
                        }
                    ],
                }
            case _:
                raise ValueError("invalid format")

    def _get_metadata(
        self, url: str, fmt: Format = Format.VIDEO_AUDIO
    ) -> MediaMetadata:
        """_get_metadata returns MediaMetadata for the given url."""
        data = MediaMetadata(url)
        with YoutubeDL(self._format_config(fmt)) as ydl:
            info = ydl.extract_info(url, download=False)

            # sanitize_info required to make serializable
            response = ydl.sanitize_info(info)
            data.name = response.get("title")
            data.author = response.get("uploader")
            data.author_url = response.get("uploader_url")
            data.ts_upload = (
                datetime.fromtimestamp(response.get("timestamp"), timezone.utc)
                if response.get("timestamp", False)
                else None
            )
            data.duration = response.get("duration")

            data.thumbnail_url = response.get("thumbnail")

            data.format = response.get("format")
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
        Commence a download from YouTube.
        Consider threading this to allow for asynchronous downloads.
        """
        opts = (
            {
                "logger": self._Queuelogger(q),
                "no_warnings": True,
                "paths": {
                    "home": directory,
                    "temp": f"{directory}/temp",  # currently hard-coded - should we make this configurable?
                },
                # Note: This will break if you were to pass in multiple target URLs
                "outtmpl": f"{filename}.%(ext)s",
            }
            | self._format_config(fmt)
        )
        try:
            # We support early metadata - send that if it's available.
            metadata = self._get_metadata(url, fmt)
            if metadata.name != "":
                event = FetcherMediaMetadataAvailable(metadata=metadata)
                q.put(event)

            with YoutubeDL(opts) as ydl:
                code = ydl.download([url])
                q.put(
                    FetcherProgressReport(
                        typ="finish",
                        level="info",
                        status=code,
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
