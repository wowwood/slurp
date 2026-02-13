import ast
import os
import tomllib
from typing import Generator

from flask import (
    Blueprint,
    Flask,
    current_app,
    render_template,
    request,
    stream_template,
)
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, URLField
from wtforms.validators import URL, AnyOf, DataRequired

from slurp.fetchers import (
    fetchers,
    fetchers_for_url,
)
from slurp.fetchers.cobalt import CobaltFetcher
from slurp.fetchers.exceptions import FetcherMisconfiguredError
from slurp.fetchers.get_iplayer import BBCiPlayerFetcher
from slurp.fetchers.types import (
    FetcherMediaMetadataAvailable,
    FetcherProgressReport,
    Format,
)
from slurp.fetchers.ytdlp import YTDLPFetcher
from slurp.helpers import format_duration


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

    return render_template("index.html", form=form, fetchers=fetchers)


def stream_fetch(url: str, format: Format, target: str, slug: str) -> Generator[str]:
    """stream_fetch is a rudimentary function that fetches the given media, yielding to generated HTML strings for progress reports."""
    fetchers = fetchers_for_url(url)
    if len(fetchers) == 0:
        yield "<article class='fetcher-outcome fetcher-progress-message-level-error'>☹️ Slurp failed - no fetchers can handle this request. Check URL?</article>"
        return

    success: bool = False
    for idx, fetcher in enumerate(fetchers):
        yield f"<code class='fetcher-progress-message'>🛫 {'Trying Fetch again' if idx > 0 else 'Fetching'} with {fetcher.name}...</code>"
        for event in fetcher.fetch(url, format, target, slug):
            match event:
                case FetcherMediaMetadataAvailable() as e:
                    # Metadata for this fetch now available.
                    yield render_template("elements/media.html", metadata=e.metadata)
                case FetcherProgressReport() as e:
                    yield render_template("elements/progress_report.html", event=e)
                    if e.typ == "finish":
                        if e.status == 0:
                            # Success
                            success = True
                        else:
                            yield f"<code><b>🛬 Fetcher failed! Reason: {e.message}</b></code>"
        if success:
            yield "<article class='fetcher-outcome fetcher-progress-message-level-success'>🥤 Media slurped</article>"
            break
    if not success:
        yield "<article class='fetcher-outcome fetcher-progress-message-level-error'>☹️ Slurp failed - out of available fetchers.</article>"

    return


@main_blueprint.post("/download")
def download():
    form = DownloadForm()
    form.directory.choices = current_app.config["OUTPUTS"]
    if not form.validate_on_submit():
        return form.errors

    return stream_template(
        "download.html",
        output=stream_fetch(
            form.url.data,
            Format[form.format.data],
            form.directory.data,
            form.slug.data,
        ),
    )


def create_app(config_filename: str = "config.toml") -> Flask:
    """Application factory."""
    app = Flask(__name__)

    # Load configuration.
    # First load the default config module, then any config file, then overload the environment.

    from slurp import config

    app.config.from_object("slurp.config.DefaultConfig")

    conf_file_load = app.config.from_file(
        os.path.join(os.getcwd(), config_filename),
        load=tomllib.load,
        text=False,
        silent=True,
    )
    if conf_file_load:
        app.logger.info("Configuration loaded from file successfully.")

    app.config.from_prefixed_env(prefix="SLURP")

    # Warn if the configuration has not been properly overloaded.
    if app.config["SECRET_KEY"] == config.DefaultConfig.SECRET_KEY:
        app.logger.warning(
            "SECRET_KEY has not been set - THIS IS NOT SECURE! Are you providing valid configuration?"
        )

    if isinstance(app.config["OUTPUTS"], str):
        app.logger.error(f"Outputs pre-split: {app.config['OUTPUTS']}")
        # Normalise the OUTPUTS list to a list
        app.config["OUTPUTS"] = app.config.get("OUTPUTS", "").split(os.pathsep)
        app.logger.error(f"Outputs post-split: {app.config['OUTPUTS']}")

    # Fill fetchers config with configured fetchers.
    if app.config.get("FETCHER_YTDLP_ENABLED") is True:
        # Scope js_runtimes correctly
        js_runtimes: dict[str, dict[str, dict[str, str]]] | None = None
        if app.config.get("FETCHER_YTDLP_JS_RUNTIMES") is not None:
            # Only try to parse the runtimes configuration if it's been set in the first place
            try:
                js_runtimes = ast.literal_eval(
                    app.config.get("FETCHER_YTDLP_JS_RUNTIMES", None)
                )
            except SyntaxError as e:
                raise SyntaxError(
                    f"Parsing FETCHER_YTDLP_JS_RUNTIMES failed: {e}"
                ) from e
        else:
            app.logger.warning(
                "The YTDLP fetcher does not have a Javascript runtime configured. "
                "It will still function, but in a degraded state - please set one using the FETCHER_YTDLP_JS_RUNTIMES config flag. "
                "If 'deno' is available on the system PATH, please ignore this warning."
            )
        try:
            fetchers.append(
                YTDLPFetcher(
                    js_runtimes=js_runtimes,
                )
            )
        except FetcherMisconfiguredError as e:
            app.logger.error("Failed to initialize the YTDLP fetcher: %s", e)

    if app.config.get("FETCHER_COBALT_ENABLED") is True:
        try:
            fetchers.append(
                CobaltFetcher(
                    app.config.get("FETCHER_COBALT_URL", "http://localhost:9000"),
                    app.config.get("FETCHER_COBALT_KEY", None),
                )
            )
        except FetcherMisconfiguredError as e:
            app.logger.error("Failed to initialize the Cobalt fetcher: %s", e)

    if app.config.get("FETCHER_BBC_IPLAYER_ENABLED") is True:
        try:
            fetchers.append(BBCiPlayerFetcher())
        except FetcherMisconfiguredError as e:
            app.logger.error("Failed to initialize the get_iplayer fetcher: %s", e)

    if len(fetchers) == 0:
        # No fetchers configured - fatal error.
        raise Exception("No fetchers enabled - please enable some!")

    app.logger.info(
        f"The following fetchers are enabled: [{', '.join([f.name for f in fetchers])}]"
    )

    app.jinja_env.filters["duration"] = format_duration

    app.register_blueprint(main_blueprint)

    return app


def serve():
    create_app().run(host="0.0.0.0", port=8000, debug=False)
