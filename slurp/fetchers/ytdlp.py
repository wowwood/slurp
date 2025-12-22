import queue
import threading
from datetime import datetime, timezone
from typing import Generator

from markupsafe import escape
from yt_dlp import YoutubeDL

from slurp.fetchers.mediametadata import MediaMetadata, Format


class YtQueueLogger:
    """ YtQueueLogger provides a yt-dlp compatible logging interface that emits exclusively to a queue."""
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

def _format_config(fmt: Format):
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

def get_metadata(url: str, format: Format = Format.VIDEO_AUDIO) -> MediaMetadata:
    data = MediaMetadata(url)
    with YoutubeDL(_format_config(format)) as ydl:
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

def _get_media(q: queue.Queue, url: str, format: Format, directory: str, filename: str):
    """
    Commence a download from Youtube.
    Consider threading this to allow for asynchronous downloads.
    """
    opts = {
        'logger': YtQueueLogger(q),
        'no_warnings': True,
        'paths': {
            'home': directory,
            'temp': f"{directory}/temp", # currently hard-coded - should we make this configurable?
        },
        # Note: This will break if you were to pass in multiple target URLs
        'outtmpl': f'{filename}.%(ext)s',
    } | _format_config(format)
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        q.put(("error", f"download exception: {e}"))
    finally:
        # signals end of stream
        q.put(None)

def get_media(url: str, format: Format, directory: str, filename: str) -> Generator[str]:
    q = queue.Queue()

    # We need to run the download on a thread so we can continue to execute our client response
    thread = threading.Thread(target=_get_media(q, url, format, directory, filename), daemon=True)
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
        yield f"<span style='{line_fmt}'>{typ}</span>: {escape(payload)}"
    yield "☑️ Download complete\n"