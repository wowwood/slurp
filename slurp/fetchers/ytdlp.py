import queue
import threading
from datetime import datetime, timezone
from typing import Generator

from markupsafe import escape
from yt_dlp import YoutubeDL

from slurp.fetchers.types import Format, Fetcher, MediaMetadata


class YTDLPFetcher(Fetcher):
    """ YTDLPFetcher is a fetcher that uses the YT-DLP library to download media exclusively from YouTube."""
    name = "yt-dlp"

    class _queueLogger:
        """ queueLogger provides a yt-dlp compatible logging interface that emits exclusively to a queue."""

        def __init__(self, q: queue.Queue):
            self.q = q

        def debug(self, msg):
            # As recommended by library documentation
            if msg.startswith('[debug] '):
                self.q.put(("debug", msg))
            else:
                self.info(msg)

        def info(self, msg):
            self.q.put(("info", msg))

        def warning(self, msg):
            self.q.put(("warn", msg))

        def error(self, msg):
            self.q.put(("error", msg))

    @classmethod
    def _format_config(cls, fmt: Format) -> dict:
        """ _format_config returns YT-DLP configuration to be used when downloading media in the given format.
        :param fmt: The desired media format.
        :return: A YT-DLP configuration parameters dictionary.
        """
        match fmt:
            case fmt.VIDEO_AUDIO:
                return {
                    'format': 'bestvideo*+bestaudio/best',
                }
                # force codec to h264 m4a/mp4
                # fails if this format isn't available, fix later
                # return ['-f', 'bv*[vcodec^=avc]+ba[ext=m4a]/b[ext=mp4]/b']
            case fmt.AUDIO_ONLY:
                return {
                    'format': 'm4a/bestaudio/best',
                    'postprocessors': [{  # Extract audio using ffmpeg
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                    }]
                }
            case _:
                raise ValueError("invalid format")

    def get_metadata(self, url: str, format: Format = Format.VIDEO_AUDIO) -> MediaMetadata:
        """ get_metadata returns MediaMetadata for the given url. """
        data = MediaMetadata(url)
        with YoutubeDL(self._format_config(format)) as ydl:
            info = ydl.extract_info(url, download=False)

            # sanitize_info required to make serializable
            response = ydl.sanitize_info(info)
            data.name = response.get('title')
            data.author = response.get('uploader')
            data.author_url = response.get('uploader_url')
            data.ts_upload = datetime.fromtimestamp(response.get('timestamp'), timezone.utc) if response.get('timestamp', False) else None
            data.duration = response.get('duration')

            data.thumbnail_url = response.get('thumbnail')

            data.format = response.get('format')
        return data

    def _get_media(self, q: queue.Queue, url: str, format: Format, directory: str, filename: str):
        """
        Commence a download from Youtube.
        Consider threading this to allow for asynchronous downloads.
        """
        opts = {
            'logger': self._queueLogger(q),
            'no_warnings': True,
            'paths': {
                'home': directory,
                'temp': f"{directory}/temp", # currently hard-coded - should we make this configurable?
            },
            # Note: This will break if you were to pass in multiple target URLs
            'outtmpl': f'{filename}.%(ext)s',
        } | self._format_config(format)
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            q.put(("error", f"download exception: {e}"))
            q.put(("finish", 1))
        finally:
            # signals end of stream
            q.put(None)

    def get_media(self, url: str, format: Format, directory: str, filename: str) -> Generator[str]:
        """ get_media downloads the media at the given params in the foreground, returning log information by means of a Generator. """
        q = queue.Queue()

        # We need to run the download on a thread so we can continue to execute our client response
        thread = threading.Thread(target=self._get_media(q, url, format, directory, filename), daemon=True)
        thread.start()

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
                        yield f"<span style='color:green'>🥤Slurp successful</span>"
                    continue
            yield f"<span style='{line_fmt}'>{typ}</span>: {escape(payload)}"