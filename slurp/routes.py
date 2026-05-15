import tempfile
from typing import Generator

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    stream_template,
)
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, URLField
from wtforms.validators import URL, AnyOf, DataRequired

from slurp.db import db
from slurp.fetchers import (
    fetchers,
    fetchers_for_url,
)
from slurp.fetchers.types import (
    FetcherMediaAvailable,
    FetcherMediaMetadataAvailable,
    FetcherProgressReport,
    Format,
)
from slurp.finaliser import finalise
from slurp.models.task import FetchTask


class DownloadForm(FlaskForm):
    url = URLField("url", validators=[DataRequired(), URL()])
    slug = StringField("slug", validators=[DataRequired()])
    format = SelectField(
        "format",
        choices=[(v.name, v.value) for v in Format],
        validators=[DataRequired(), AnyOf([v.name for v in Format])],
    )
    directory = SelectField("directory", validators=[DataRequired()])


main_blueprint = Blueprint("main", __name__, template_folder="templates")


@main_blueprint.get("/")
def index():
    form = DownloadForm(request.args)
    form.directory.choices = current_app.config["OUTPUTS"]
    allTasks = db.session.execute(db.select(FetchTask)).scalars()

    return render_template(
        "index.html", form=form, fetchers=fetchers, allTasks=allTasks
    )


def stream_fetch(url: str, format: Format, target: str, slug: str) -> Generator[str]:
    """stream_fetch is a rudimentary function that fetches the given media, yielding to generated HTML strings for progress reports."""
    fetchers = fetchers_for_url(url)
    if len(fetchers) == 0:
        yield "<article class='fetcher-outcome fetcher-progress-message-level-error'>☹️ Slurp failed - no fetchers can handle this request. Check URL?</article>"
        return

    # Work in a temporary directory that gets torn down at the completion of this slurp run
    with tempfile.TemporaryDirectory(
        dir=current_app.config.get("OUTPUT_TEMP", None)
    ) as tmp_dir:
        success: bool = False
        media_path: str | None = None
        for idx, fetcher in enumerate(fetchers):
            yield f"<code class='fetcher-progress-message'>🛫 {'Trying Fetch again' if idx > 0 else 'Fetching'} with {fetcher.name}...</code>"
            for event in fetcher.fetch(url, format, tmp_dir, slug):
                match event:
                    case FetcherMediaMetadataAvailable() as e:
                        # Metadata for this fetch now available.
                        yield render_template(
                            "elements/media.html", metadata=e.metadata
                        )
                    case FetcherMediaAvailable() as e:
                        media_path = e.path
                    case FetcherProgressReport() as e:
                        yield render_template("elements/progress_report.html", event=e)
                        if e.typ == "finish":
                            if e.status == 0:
                                # Success
                                success = True
                            else:
                                yield f"<code><b>🛬 Fetcher failed! Reason: {e.message}</b></code>"

            if success:
                yield "<article class='fetcher-outcome fetcher-progress-message-level-success'>✅ Media fetch successful</article>"
                break
        if not success:
            yield "<article class='fetcher-outcome fetcher-progress-message-level-error'>☹️ Slurp failed - out of available fetchers.</article>"

        # Run the finalisers.
        yield "<article class='fetcher-outcome fetcher-progress-message-level-info'>🚚 Finalising slurp...</article>"
        final_path: str | None = None
        try:
            for event in finalise(media_path, target):
                match event:
                    case FetcherProgressReport() as e:
                        yield render_template("elements/progress_report.html", event=e)
                    case FetcherMediaAvailable() as e:
                        final_path = e.path
        except Exception as e:
            yield f"<article class='fetcher-outcome fetcher-progress-message-level-error'>💣 Failed to finalise media: {e}</article>"
            return
        yield f"<article class='fetcher-outcome fetcher-progress-message-level-success'>🥤 Media slurped to {final_path}</article>"
        return


def fetch_job_create(url: str, format: Format, target: str, slug: str) -> FetchTask:
    """
    Create a FetchTask.
    :param url: The URL of the media to be fetched.
    :param format: The desired format to grab the media in.
    :param target: The target directory to create the media in.
    :param slug: The desired filename for ingest.
    :return: Committed FetchTask.
    """
    task = FetchTask(url=url, format=format, target=target, slug=slug)
    db.session.add(task)
    db.session.commit()

    return task


def fetch_work(task: FetchTask) -> Generator[str]:
    """
    Perform the work described in the given FetchTask.
    :param task: FetchTask to be executed.
    :return: Generator
    """
    # This is the beginnings of what will be the task runner thread.
    # Right now it just wraps the HTML generator in some database updates - but eventually
    # this will simply take the task ID, pull it from DB, then trust those details
    # to complete the fetch - putting assoc. events onto the event bus.
    task.status = FetchTask.TaskStatus.running
    db.session.add(task)
    db.session.commit()
    yield from stream_fetch(
        url=task.url, format=task.format, target=task.target, slug=task.slug
    )
    # We don't yet support success / failure states with this setup, so just return the special "completed" state.
    # This will improve dramatically with further work on #29
    task.status = FetchTask.TaskStatus.completed
    db.session.add(task)
    db.session.commit()

    return


@main_blueprint.post("/download")
def download():
    """
    Fetch, slug, and expose the media content described in the given form details.
    :return: HTML streaming response.
    """
    form = DownloadForm()
    form.directory.choices = current_app.config["OUTPUTS"]
    if not form.validate_on_submit():
        return form.errors
    task = fetch_job_create(
        form.url.data,
        Format[form.format.data],
        form.directory.data,
        form.slug.data,
    )
    return stream_template(
        "download.html",
        output=fetch_work(task),
    )
