import datetime
import enum

from flask_sse import sse
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

    # The path to the output file - only set if the fetch succeeded.
    # If pruned is set, this path most likely does not exist, and is for information only.
    output_path: str | None = None

    # Whether this fetch has had its output data removed from the filesystem.
    pruned: bool = Field(index=True, default=False)

    # Whether this fetch has had its logs and events destroyed.
    purged: bool = Field(index=True, default=False)

    def lock(self, *args, **kwargs):
        return self.db().lock(name=self.pk, *args, **kwargs)

    def emit_event(self, typ: str, level: str, message: str, status: int = 0):
        db_log = FetchEvent(
            fetch_id=self.pk,
            typ=typ,
            level=level,
            message=message,
            status=status,
        )
        db_log.save()
        sse.publish(db_log.model_dump_json())


class FetchEvent(BaseModel, index=True):
    fetch_id: str = Field(index=True)
    typ: str
    level: str
    message: str
    status: int = 0
