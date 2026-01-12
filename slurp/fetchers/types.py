from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generator


class Format(Enum):
    """ A Format defines what format the targetted Media should be fetched in. """
    VIDEO_AUDIO = "Video+Audio"
    VIDEO_ONLY  = "Video Only (muted)"
    AUDIO_ONLY  = "Audio Only"

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


class Fetcher:
    """ A Fetcher is an interface for downloading media from any supported external media source.

    Attributes:
        name: Friendly name of the Fetcher
        service_names: list[str]: Friendly names of services this fetcher supports.
        service_urls: list[str] | None: List of domains that this fetcher supports grabbing media from.
            If set to None, then this service will attempt to download literally anything as a last resort.
    """

    name: str

    service_names: list[str]

    service_urls: list[str] | None

    def get_metadata(self, url: str, fmt: Format) -> MediaMetadata | None:
        """
        get_metadata fetches ONLY metadata about the media at the given URL.
        This is used to provide early metadata information.
        :param url: Target URL
        :param fmt: The desired media scrape format.
        :return: A MediaMetadata object, or None if it is not possible to retrieve early media metadata.
        """
        pass

    def get_media(self, url: str, fmt: Format, directory: str, filename: str) -> Generator[str]:
        """
        get_media fetches the media at the given URL, in the given format, and places it at the provided directory / filename.
        :param url:
        :param fmt:
        :param directory:
        :param filename:
        """
        pass
