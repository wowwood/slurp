from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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


class Format(Enum):
    VIDEO_AUDIO = "Video+Audio"
   # VIDEO_ONLY  = "Video Only" - not needed tbh
    AUDIO_ONLY  = "Audio Only"
