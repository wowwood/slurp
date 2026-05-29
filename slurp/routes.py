from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
)
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, URLField
from wtforms.validators import URL, AnyOf, DataRequired

from slurp.fetchers import (
    fetchers,
)
from slurp.fetchers.types import (
    Format,
)
from slurp.models.task import Fetch, FetchEvent


class DownloadForm(FlaskForm):
    url = URLField("url", validators=[DataRequired(), URL()])
    slug = StringField("slug", validators=[DataRequired()])
    format = SelectField(
        "format",
        choices=[(v.name, v.value) for v in Format],
        validators=[DataRequired(), AnyOf([v.name for v in Format])],
    )
    target = SelectField("target", validators=[DataRequired()])


main_blueprint = Blueprint("main", __name__, template_folder="templates")


@main_blueprint.get("/")
def index():
    form = DownloadForm(request.args)
    form.target.choices = current_app.config["OUTPUTS"]
    allTasks = Fetch.find().sort_by("-ts_updated").page(offset=0, limit=10)

    return render_template(
        "index.html", form=form, fetchers=fetchers, allTasks=allTasks
    )


@main_blueprint.get("/fetch/<id>")
def fetch_info(id: str):
    form = DownloadForm(request.args)
    form.target.choices = current_app.config["OUTPUTS"]
    task = Fetch.get(id)
    if task is None:
        return abort(404)
    allLog = FetchEvent.find(FetchEvent.fetch_id == id).sort_by("ts_created").all()

    return render_template("fetch.html", fetch=task, fetchLog=allLog)
