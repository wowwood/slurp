import os
import tomllib

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

from slurp.fetchers import CobaltFetcher, YTDLPFetcher, determine_fetcher, fetchers
from slurp.fetchers.types import Format
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


@main_blueprint.post("/download")
def download():
    form = DownloadForm()
    form.directory.choices = current_app.config["OUTPUTS"]
    if not form.validate_on_submit():
        return form.errors

    try:
        fetcher = determine_fetcher(form.url.data)
    except ValueError as e:
        return str(e), 400

    return stream_template(
        "download.html",
        fetcher=fetcher,
        metadata=fetcher.get_metadata(form.url.data, Format[form.format.data]),
        output=fetcher.get_media(
            form.url.data, Format[form.format.data], form.directory.data, form.slug.data
        ),
    )


def create_app(config_filename: str = "config.toml") -> Flask:
    app = Flask(__name__)
    # app.config.from_prefixed_env(prefix='YDP')
    app.config.from_file(
        os.path.join(os.getcwd(), config_filename), load=tomllib.load, text=False
    )
    app.config["OUTPUTS"] = app.config.get("OUTPUTS", "").split(os.pathsep)

    # Fill fetchers config with configured fetchers.
    if app.config.get("FETCHER_YTDLP_ENABLED") is True:
        app.logger.info("YTDLP fetcher enabled")
        fetchers.append(YTDLPFetcher())

    if app.config.get("FETCHER_COBALT_ENABLED") is True:
        app.logger.info("Cobalt fetcher enabled")
        fetchers.append(
            CobaltFetcher(
                app.config.get("FETCHER_COBALT_URL", "http://localhost:9000"),
                app.config.get("FETCHER_COBALT_KEY", None),
            )
        )

    if len(fetchers) == 0:
        # No fetchers configured - fatal error.
        raise Exception("No fetchers enabled")

    app.jinja_env.filters["duration"] = format_duration

    app.register_blueprint(main_blueprint)

    return app


def serve():
    create_app().run(host="0.0.0.0", port=8000, debug=False)
