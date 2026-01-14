from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generator


class Format(Enum):
    """A Format defines what format the target Media should be fetched in."""

    VIDEO_AUDIO = "Video+Audio"
    VIDEO_ONLY = "Video Only (muted)"
    AUDIO_ONLY = "Audio Only"


@dataclass()
class MediaMetadata:
    """MediaMetadata is a source-agnostic representation of any media available to be fetched."""

    url: str
    name: str = "Unknown Name"

    author: str = "Unknown Author"
    author_url: str | None = None

    ts_upload: datetime | None = None

    duration: str = "Unknown Duration"

    format: str = "Unknown Format"

    thumbnail_url: str | None = None


class FetcherUpdateEvent(ABC):
    """A FetcherUpdateEvent is any event that happens over the course of a fetcher's fetching lifespan."""

    pass


@dataclass()
class FetcherProgressReport(FetcherUpdateEvent):
    """FetcherProgressReport is a FetcherUpdateEvent representing a report of progress, new data, or a log message."""

    typ: str
    level: str
    message: str
    status: int = 0


@dataclass()
class FetcherMediaMetadataAvailable(FetcherUpdateEvent):
    """FetcherMediaMetadataAvailable is a FetcherUpdateEvent fired when the metadata of the given media is available."""

    metadata: MediaMetadata


class Fetcher(ABC):
    """A Fetcher is an interface for downloading media from any supported external media source.

    Attributes:
        name: Friendly name of the Fetcher
        priority: How urgently this Fetcher should be selected (0 has highest priority, then incrementing)
        service_names: list[str]: Friendly names of services this fetcher supports.
        service_urls: list[str] | None: List of domains that this fetcher supports grabbing media from.
            If set to None, then this service will attempt to download literally anything as a last resort.
    """

    name: str

    priority: int

    service_names: list[str]

    service_urls: list[str] | None

    @property
    @abstractmethod
    def ready(self) -> bool:
        """A Fetcher is Ready when it can handle requests (configuration is valid, can connect to backend, etc."""
        return False

    @abstractmethod
    def fetch(
        self,
        url: str,
        fmt: Format,
        directory: str,
        filename: str,
    ) -> Generator[FetcherUpdateEvent]:
        """
        fetch fetches the media at the given URL, in the given format, and places it at the provided directory / filename.
        Updates are provided over the returned generator.

        If early metadata for the given media is available, return a MediaMetadata object.
        Otherwise, return FetcherProgress objects.
        :param url:
        :param fmt:
        :param directory:
        :param filename:
        """
        pass
