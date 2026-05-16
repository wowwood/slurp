import tempfile

from celery import Task, shared_task
from flask import current_app
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from werkzeug.exceptions import BadRequest

from slurp.db import db
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


@shared_task(
    bind=True, dont_autoretry_for=(NoResultFound, MultipleResultsFound, BadRequest)
)
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
    task.status = Fetch.TaskStatus.running
    task.worker_id = self.request.id
    db.session.add(task)
    db.session.commit()

    self.update_state(state=Fetch.TaskStatus.running.value)

    db.session.add(task)
    db.session.commit()

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
                for event in fetcher.fetch(task.url, task.format, tmp_dir, task.slug):
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
                            db.session.add(task)
                            db.session.commit()
                        case FetcherMediaAvailable() as e:
                            media_path = e.path
                        case FetcherProgressReport() as e:
                            self.update_state(event=e)
                            if e.typ == "finish":
                                if e.status == 0:
                                    # Success
                                    success = True
                                else:
                                    self.update_state(
                                        event=f"Fetcher failed! Reason: {e.message}"
                                    )
                                    # yield f"<code><b>🛬 Fetcher failed! Reason: {e.message}</b></code>"

                if success:
                    break
            if not success:
                # yield "<article class='fetcher-outcome fetcher-progress-message-level-error'>☹️ Slurp failed - out of available fetchers.</article>"
                raise FetchersExhaustedError

            # Run the finaliser.
            self.update_state(event="Finalising...")
            final_path: str | None = None
            try:
                for event in finalise(media_path, task.target):
                    match event:
                        case FetcherProgressReport() as e:
                            self.update_state(event=e)
                        case FetcherMediaAvailable() as e:
                            final_path = e.path
            except Exception as e:
                # yield f"<article class='fetcher-outcome fetcher-progress-message-level-error'>💣 Failed to finalise media: {e}</article>"
                raise FinaliserError(e)
            # yield f"<article class='fetcher-outcome fetcher-progress-message-level-success'>🥤 Media slurped to {final_path}</article>"
    except Exception as e:
        self.update_state(status=Fetch.TaskStatus.failed.value, reason=str(e))
        task.status = Fetch.TaskStatus.failed
        db.session.add(task)
        db.session.commit()
        raise e

    self.update_state(status=Fetch.TaskStatus.success.value, path=final_path)
    task.status = Fetch.TaskStatus.success
    db.session.add(task)
    db.session.commit()

    return final_path
