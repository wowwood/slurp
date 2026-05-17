import datetime
import enum

from redis_om import Field

from slurp.fetchers.types import Format
from slurp.models.base import BaseModel


class FetchMetadata(BaseModel):
    name: str | None = None

    author: str | None = None

    ts_upload: datetime.datetime | None = None

    duration: int | None = None

    format: str | None = None

    thumbnail_url: str | None = None

    class Meta:
        embedded = True


class Fetch(BaseModel, index=True):
    url: str = Field(index=True)
    slug: str = Field(index=True)
    target: str | None = None
    format: Format = Format.VIDEO_AUDIO

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

    status: TaskStatus = TaskStatus.unknown

    meta: FetchMetadata | None = None

    # The ID of the celery task.
    worker_id: str | None = Field(index=True, default=None)

    def lock(self):
        return self.db().lock(name=self.pk)
