import enum

from sqlalchemy.orm import Mapped, mapped_column

from slurp.fetchers.types import Format
from slurp.models.base import BaseModel


class FetchTask(BaseModel):
    # URL is the fully qualified link to the media to be fetched.
    url: Mapped[str] = mapped_column(index=True)
    # Slug is the desired output media name.
    slug: Mapped[str] = mapped_column(index=True)
    # Target is the desired destination identifier. If not set, uses the app-configured default.
    target: Mapped[str | None] = mapped_column()

    # Format is the desired format to fetch the URL in.
    format: Mapped[Format] = mapped_column(
        default=Format.VIDEO_AUDIO.value,
        nullable=False,
    )

    class TaskStatus(str, enum.Enum):
        # "created" tasks are awaiting processing or assignment to a worker.
        created = "created"
        # "Running" tasks are in the process of being fetched.
        running = "running"
        # "Success" tasks completed their fetch successfully.
        success = "success"
        # "Failed" tasks failed to process for some reason.
        failed = "failed"
        # "Completed" tasks is one where it finished executing, but we don't know the outcome for some reason.
        completed = "completed"
        # "Unknown" tasks are ones where the execution state is a mystery to us.
        unknown = "unknown"

    # Status
    status: Mapped[TaskStatus] = mapped_column(
        default=TaskStatus.created.value,
        nullable=False,
    )

    # TODO should there be a mutex here?
