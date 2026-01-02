from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generator


class Format(Enum):
    """ A Format defines what format the targetted Media should be fetched in. """
    VIDEO_AUDIO = "Video+Audio"
   # VIDEO_ONLY  = "Video Only" - not needed tbh
    AUDIO_ONLY  = "Audio Only"


class Fetcher:
    """ A Fetcher is an interface for downloading media from any supported external media source.

    Attributes:
        name: Friendly name of the Fetcher
    """

    name: str

    def get_metadata(self, url: str, format: Format) -> MediaMetadata:
        """
        get_metadata fetches ONLY metadata about the media at the given URL.
        :param url: Target URL
        :param format: The desired media scrape format.
        """
        pass

    def get_media(self, url: str, format: Format, directory: str, filename: str) -> Generator[str]:
        """
        get_media fetches the media at the given URL, in the given format, and places it at the provided directory / filename.
        :param url:
        :param format:
        :param directory:
        :param filename:
        """
        pass


@dataclass()
class MediaMetadata:
    """ MediaMetadata is a source-agnostic representation of any media available to be fetched. """
    url: str
    name: str = 'Unknown Name'

    author: str = 'Unknown Author'
    author_url: str | None = None

    ts_upload: datetime | None = None

    duration: str = 'Unknown Duration'

    format: str = 'Unknown Format'

    thumbnail_url: str | None = None
