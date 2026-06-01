import datetime
import pathlib
import tempfile

from celery import Celery, Task, shared_task
from celery.exceptions import InvalidTaskError
from celery.schedules import crontab
from flask import current_app
from flask_sse import sse
from werkzeug.exceptions import BadRequest

from slurp.exceptions import FinaliserError
from slurp.fetchers import fetchers_for_url
from slurp.fetchers.exceptions import (
    FetchersExhaustedError,
    NoFetchersAvailable,
)
from slurp.fetchers.types import (
    FetcherMediaAvailable,
    FetcherMediaMetadataAvailable,
    FetcherProgressReport,
    Format,
)
from slurp.finaliser import finalise
from slurp.models import Fetch, FetchMetadata
from slurp.models.task import FetchEvent


@shared_task(bind=True, dont_autoretry_for=(BadRequest,))
def fetch(self: Task, url: str, format: Format, target: str, slug: str) -> str:
    """
    Fetch the given media from the network.
    :param self: Celery task object.
    :param url: Target URL.
    :param format: Format to perform the download in.
    :param target: Target output directory. Must be configured.
    :param slug: Output filename.
    :return: Absolute path to where the successfully fetched media resides.
    """

    # Safety: Validate the destination is permitted
    if target not in current_app.config["OUTPUTS"]:
        raise BadRequest(
            "This target is not valid. Please refer to Slurp's configuration."
        )

    task = Fetch(
        url=url,
        format=format,
        target=target,
        slug=slug,
    )
    # This assertion is mainly here to clear some IDE warnings.
    assert task.target is not None, "task target must be set"
    task.status = Fetch.TaskStatus.running
    task.worker_id = self.request.id
    task.save()

    lock = task.lock()
    try:
        lock.acquire(token=self.request.id)

        sse.publish(
            {
                "task_id": task.pk,
                "url": task.url,
                "format": format,
                "target": target,
                "slug": slug,
            },
            type="created_data",
        )
        task.emit_event("created", "info", f"Running task {task.pk}")

        # Perform the fetch.
        # yield from stream_fetch(
        #     url=task.url, format=task.format, target=task.target, slug=task.slug
        # )
        try:
            fetchers = fetchers_for_url(task.url)
            if len(fetchers) == 0:
                raise NoFetchersAvailable

            # Work in a temporary directory that gets torn down at the completion of this slurp run
            with tempfile.TemporaryDirectory(
                dir=current_app.config.get("OUTPUT_TEMP", None)
            ) as tmp_dir:
                success: bool = False
                media_path: str | None = None
                for idx, fetcher in enumerate(fetchers):
                    # yield f"<code class='fetcher-progress-message'>🛫 {'Trying Fetch again' if idx > 0 else 'Fetching'} with {fetcher.name}...</code>"
                    self.update_state(
                        event=f"{'Trying Fetch again' if idx > 0 else 'Fetching'} with {fetcher.name}"
                    )
                    sse.publish(
                        {
                            "fetch_id": task.pk,
                            "message": f"{'Trying Fetch again' if idx > 0 else 'Fetching'} with {fetcher.name}",
                        },
                        type="message",
                    )
                    task.emit_event(
                        "log",
                        "info",
                        f"{'Trying Fetch again' if idx > 0 else 'Fetching'} with {fetcher.name}",
                    )
                    for event in fetcher.fetch(
                        task.url, task.format, tmp_dir, task.slug
                    ):
                        match event:
                            case FetcherMediaMetadataAvailable() as e:
                                # Metadata for this fetch now available.
                                self.update_state(metadata=e.metadata)
                                db_meta = FetchMetadata(
                                    name=e.metadata.name,
                                    author=e.metadata.author,
                                    author_url=e.metadata.author_url,
                                    ts_upload=e.metadata.ts_upload,
                                    duration=e.metadata.duration,
                                    format=e.metadata.format,
                                    thumbnail_url=e.metadata.thumbnail_url,
                                )
                                task.meta = db_meta
                                task.save()
                                sse.publish(
                                    {
                                        "fetch_id": task.pk,
                                        "meta": db_meta.model_dump_json(),
                                    },
                                    type="metadata",
                                )
                                task.emit_event(
                                    "log",
                                    "info",
                                    "Metadata successfully fetched",
                                )
                            case FetcherMediaAvailable() as e:
                                media_path = e.path
                            case FetcherProgressReport() as e:
                                self.update_state(event=e)
                                task.emit_event(e.typ, e.level, e.message, e.status)

                                if e.typ == "finish":
                                    if e.status == 0:
                                        # Success
                                        success = True
                                    else:
                                        task.emit_event(
                                            "log",
                                            "error",
                                            f"Fetcher failed: {e.message}",
                                        )
                                        # yield f"<code><b>🛬 Fetcher failed! Reason: {e.message}</b></code>"

                    if success:
                        break
                if not success:
                    # yield "<article class='fetcher-outcome fetcher-progress-message-level-error'>☹️ Slurp failed - out of available fetchers.</article>"
                    raise FetchersExhaustedError

                assert media_path is not None, (
                    "fetcher reported success yet media_path is None"
                )

                # Run the finaliser.
                self.update_state(event="Finalising...")
                final_path: str | None = None
                try:
                    for event in finalise(media_path, task.target):
                        match event:
                            case FetcherProgressReport() as e:
                                self.update_state(event=e)
                                task.emit_event(e.typ, e.level, e.message, e.status)
                            case FetcherMediaAvailable() as e:
                                final_path = e.path
                except Exception as e:
                    # yield f"<article class='fetcher-outcome fetcher-progress-message-level-error'>💣 Failed to finalise media: {e}</article>"
                    raise FinaliserError(e)
                # yield f"<article class='fetcher-outcome fetcher-progress-message-level-success'>🥤 Media slurped to {final_path}</article>"
        except Exception as e:
            self.update_state(status=Fetch.TaskStatus.failed.value, reason=str(e))
            task.status = Fetch.TaskStatus.failed
            task.save()
            sse.publish(
                {
                    "fetch_id": task.pk,
                    "state": Fetch.TaskStatus.failed.value,
                    "message": str(e),
                },
                type="status",
            )
            task.emit_event(
                "log",
                "error",
                f"Fetch failed: {e}",
            )
            raise e

        assert final_path is not None, "final_path not properly set by fetcher routine"
        self.update_state(status=Fetch.TaskStatus.success.value, path=final_path)
        task.status = Fetch.TaskStatus.success.value
        task.output_path = final_path
        task.save()
        sse.publish(
            {
                "fetch_id": task.pk,
                "state": Fetch.TaskStatus.success.value,
                "path": final_path,
            },
            type="status",
        )
        task.emit_event(
            "log",
            "success",
            f"Fetch succeeded: file saved to {final_path}",
        )

        return final_path
    finally:
        # Always release the lock to avoid a deadlock.
        lock.release()


@shared_task(bind=True, ignore_result=False)
def cleanup_stale_tasks(self):
    """
    cleanup_stale_tasks removes persistent data about tasks that exceed the configured TASK_STALE duration.
    :param self:
    :return:
    """
    # Get the timestamp of the desired cutoffs.
    # TODO configurable
    # The PRUNE cutoff simply destroys the output data blob.
    prune_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        hours=current_app.config.get("PRUNE_AFTER")
    )
    # The PURGE cutoff destroys all event data, leaving only the metadata.
    purge_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        hours=current_app.config.get("PURGE_AFTER")
    )

    # Find all tasks that are OLDER than the cutoff, and that have not been purged.
    # Purged is done as a negative to catch models without the key set
    prune_targets = Fetch.find(
        (Fetch.ts_created <= prune_cutoff) & ~(Fetch.purged == True),  # noqa: E712
    ).all()
    for task in prune_targets:
        # Enqueue cleanup
        # Could do this shorthand however it's (IMO) easier to read this way
        if task.ts_created < purge_cutoff:
            # PURGE the task.
            cleanup_task.delay(task.pk, events=True)
        else:
            # PRUNE the task.
            cleanup_task.delay(task.pk, events=False)
    ids = [t.pk for t in prune_targets]
    return ids


@shared_task(bind=True)
def cleanup_task(self, task_pk: str, events: bool = False):
    """
    cleanup_task removes data about the given task from the database, and attempts to remove any files related to the fetch.
    :param self:
    :param task_pk: ID of the task.
    :param events: Destroy all logs and events relating to this task. This is a PURGE.
    :return:
    """
    task = Fetch.find(Fetch.pk == task_pk).first()
    if not task:
        raise InvalidTaskError(f"Task {task_pk} does not exist on database")

    # Destroy any events relating to the task if requested
    if events:
        FetchEvent.find(FetchEvent.fetch_id == task_pk).delete()
        task.purged = True

    # Destroy the resultant file in the filesystem, if it's there
    if task.output_path is not None:
        fs_target = pathlib.Path(task.output_path)
        if fs_target.is_file():
            fs_target.unlink()
        else:
            print("Failed to destroy output - does not exist, or is not a file")
    # Mark the task as pruned
    task.pruned = True
    task.save()

    # Raise SSE event / add to the log that the prune occurred
    task.emit_event(
        ("purge" if events else "prune"),
        "info",
        f"Task was {'purged' if events else 'pruned'}",
        0,
    )
    return


def _init_periodic_tasks(sender: Celery, **kwargs):
    # Clean up stale tasks every hour.
    sender.add_periodic_task(
        # Run hourly, on the hour.
        crontab(minute=0),
        cleanup_stale_tasks.s(),
    )
