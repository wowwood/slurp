import enum

from sqlalchemy import text
from sqlmodel import Field

from slurp.models.base import BaseModel


class FetchTask(BaseModel, table=True):
    # URL is the fully qualified link to the media to be fetched.
    url: str = Field(index=True)
    # Slug is the desired output media name.
    slug: str = Field(index=True)

    class FetchFormat(int, enum.Enum):
        video_audio = 0
        video_only = 1
        audio_only = 2

    # Format is the desired format to fetch the URL in.
    format: FetchFormat = Field(
        sa_column_kwargs={"server_default": text(f"'{FetchFormat.video_audio.value}'")},
        default=FetchFormat.video_audio.value,
        nullable=False,
    )
    # Target is the desired destination identifier. If not set, uses the app-configured default.
    target: str | None

    class TaskStatus(str, enum.Enum):
        created = "created"
        running = "running"
        success = "success"
        failed = "failed"

    # Status
    status: TaskStatus = Field(
        sa_column_kwargs={"server_default": text(f"'{TaskStatus.created.value}'")},
        default=TaskStatus.created.value,
        nullable=False,
    )

    # TODO should there be a mutex here?
