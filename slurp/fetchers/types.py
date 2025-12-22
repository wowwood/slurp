from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generator


class Format(Enum):
    VIDEO_AUDIO = "Video+Audio"
   # VIDEO_ONLY  = "Video Only" - not needed tbh
    AUDIO_ONLY  = "Audio Only"


class Fetcher:
    name: str

    def get_metadata(self, url: str, format: Format) -> MediaMetadata:
        pass

    def get_media(self, url: str, format: Format, directory: str, filename: str) -> Generator[str]:
        pass


@dataclass()
class MediaMetadata:
    url: str
    name: str = 'Unknown Name'

    author: str = 'Unknown Author'
    author_url: str | None = None

    ts_upload: datetime | None = None

    duration: str = 'Unknown Duration'

    format: str = 'Unknown Format'

    thumbnail_url: str | None = None
