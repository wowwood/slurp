from datetime import datetime, timezone

from yt_dlp import YoutubeDL

from slurp.fetchers.mediametadata import MediaMetadata


def GetMetadata(url: str) -> MediaMetadata:
    data = MediaMetadata(url)
    with YoutubeDL() as ydl:
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