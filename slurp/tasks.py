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
from slurp.fetchers.exceptions import (
    FetchersExhaustedError,
    FetchLockedError,
    NoFetchersAvailable,
)
from slurp.fetchers.types import (
    FetcherMediaAvailable,
    FetcherMediaMetadataAvailable,
    FetcherProgressReport,
)
from slurp.finaliser import finalise, troubleshooter
from slurp.models import Fetch, FetchMetadata
from slurp.models.task import FetchEvent


@shared_task(
    name="slurp.create_fetch",
    bind=True,
    dont_autoretry_for=(BadRequest,),
    ignore_result=False,
)
def create_fetch(self: Task, url: str, fmt: str, target: str, slug: str) -> str:
    """
    Create and enqueue the given media for fetching.
    :param self: Celery task object.
    :param url: Target URL.
    :param fmt: Format to perform the download in as defined by fetchers.types.Format.
    :param target: Target output directory. Must be configured.
    :param slug: Output filename.
    :return: Fetch PK.
    """
    # Safety: Validate the destination is permitted
    if target not in current_app.config["OUTPUTS"]:
        raise BadRequest(
            "This target is not valid. Please refer to Slurp's configuration."
        )

    task = Fetch(
        url=url,
        format=fmt,
        target=target,
        slug=slug,
    )
    task.status = Fetch.TaskStatus.created
    task.worker_id = self.request.id
    task.save()
    assert task.pk is not None, "task pk was not set by flush"

    sse.publish(
        {
            "task_id": task.pk,
            "url": task.url,
            "format": task.format,
            "target": task.target,
            "slug": task.slug,
        },
        type="task_created",
    )

    # Enqueue.
    fetch.delay(
        pk=task.pk,
    )
    return task.pk


@shared_task(
    name="slurp.fetch", bind=True, dont_autoretry_for=(BadRequest,), acks_late=True
)
def fetch(self: Task, pk: str):
    """
    Work the given fetch task, by downloading the media from the web, finalising it to the defined location.
    It is not intended to call this task directly - it is automatically enqueued by create_fetch.
    :param self: Celery task object.
    :param pk: Primary Key of the task in the database.
    :return: None
    """

    task = Fetch.find(Fetch.pk == pk).first()
    if not task:
        raise BadRequest(f"Task {pk} does not exist on database")

    # This assertion is mainly here to clear some IDE warnings.
    assert task.target is not None, "task target must be set"

    # Re-validate that the destination is permitted for extra safety - just in case the database has been tampered with
    if task.target not in current_app.config["OUTPUTS"]:
        raise BadRequest(
            "This target is not valid. Please refer to Slurp's configuration."
        )

    # We take a lock to ensure that we're the only thing working with the given Fetch.
    # If multiple workers were working the same fetch, not only is it a waste of resources, but
    # there's a very real possibility they may end up corrupting
    # the output file once it's written to disk.
    lock = task.lock(blocking=False)
    try:
        l_success = lock.acquire(token=self.request.id)
        if not l_success:
            raise FetchLockedError

        # Update the task status
        task.status = Fetch.TaskStatus.running
        task.worker_id = self.request.id
        task.save()
        task.emit_event("log", "info", f"Task acquired by job {self.request.id}")

        try:
            # Find all fetchers valid for the fetch URL
            fetchers = current_app.extensions["fetchers"].get_for_url(task.url)
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
                    # Call the fetcher module, and receive events from it
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

                # Safety assertion
                assert media_path is not None, (
                    "fetcher reported success yet media_path is None"
                )

                # The fetcher seems to have worked - run the finaliser.
                self.update_state(event="finalising")
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
            # Catch exceptions and set the task state appropriately.
            # Before that, run the troubleshooter to see if there's a reason the error happened.
            task.emit_event("log", "info", "Attempting to troubleshoot...")
            for event in troubleshooter(task):
                match event:
                    case FetcherProgressReport() as trbl_msg:
                        task.emit_event(
                            trbl_msg.typ,
                            trbl_msg.level,
                            trbl_msg.message,
                            trbl_msg.status,
                        )
            raise e

        assert final_path is not None, "final_path not properly set by fetcher routine"
        # Update the fetch with the final state.
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
            type="fetch_updated",
        )
        task.emit_event(
            "log",
            "success",
            f"Fetch succeeded: file saved to {final_path}",
        )

        return final_path
    except Exception as e:
        # Mark the task failed and re-raise
        self.update_state(status=Fetch.TaskStatus.failed.value, reason=str(e))
        task.status = Fetch.TaskStatus.failed
        task.save()
        sse.publish(
            {
                "fetch_id": task.pk,
                "state": Fetch.TaskStatus.failed.value,
                "message": str(e),
            },
            type="fetch_updated",
        )
        task.emit_event(
            "log",
            "error",
            f"Fetch failed: {e}",
        )
        raise e
    finally:
        # Always release the lock to avoid a deadlock.
        lock.release()


@shared_task(name="slurp.cleanup_stale_tasks", bind=True, ignore_result=False)
def cleanup_stale_tasks(self):
    """
    cleanup_stale_tasks removes persistent data about tasks that exceed the configured TASK_STALE duration.
    :param self:
    :return: A list of IDs affected by the task
    """
    # Get the timestamp of the desired cutoffs.
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


@shared_task(name="slurp.cleanup_task", bind=True)
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
