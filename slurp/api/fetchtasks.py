from flask import current_app
from flask_restx import Namespace, Resource, ValidationError, fields

from slurp.db import db
from slurp.fetchers.types import Format
from slurp.models.task import Fetch
from slurp.tasks import fetch

api = Namespace("task", description="Fetch tasks")


class __EnumValue(fields.Raw):
    def format(self, value):
        return value.value


fetchMetadata = api.model(
    "FetchMetadata",
    {
        "name": fields.String(description="Name of the media"),
        "author": fields.String(description="Author of the media"),
        "author_url": fields.String(
            description="The URL where the author of this media can be found"
        ),
        "ts_upload": fields.DateTime(description="Time when the media was uploaded"),
        "duration": fields.Integer(description="Duration of the media in seconds"),
        "format": fields.String(
            description="Descriptive format of the format that the media will be downloaded in"
        ),
        "thumbnail_url": fields.String(description="Thumbnail url"),
    },
)

fetchTask = api.model(
    "FetchTask",
    {
        "id": fields.Integer(description="ID of task"),
        "ts_created": fields.DateTime(description="Created time"),
        "ts_updated": fields.DateTime(description="Last updated time"),
        "url": fields.String(description="URL that task fetches"),
        "slug": fields.String(description="Slug to save fetch as"),
        "format": __EnumValue(description="Download format"),
        "target": fields.String(description="Filesystem target identifier"),
        "status": __EnumValue(description="Task status"),
        "meta": fields.Nested(fetchMetadata, default={}),
        "worker_id": fields.String(description="Work ID - use to query work status"),
    },
)

createTask = api.model(
    "CreateTask",
    {
        "url": fields.String(description="URL that should be fetched", required=True),
        "format_video": fields.Boolean(
            description="Download the video element of this media", default=True
        ),
        "format_audio": fields.Boolean(
            description="Download the audio element of this media", default=True
        ),
        "slug": fields.String(description="Slug to save fetch as", required=True),
        "target": fields.String(
            description="Filesystem target identifier. This MUST be a valid destination as configured.",
            required=True,
        ),  # make this not required?
    },
)


@api.route("/")
class TaskList(Resource):
    @api.doc("list_tasks")
    @api.marshal_list_with(fetchTask)
    def get(self):
        fetches = db.session.execute(db.select(Fetch)).scalars().all()
        return fetches

    @api.doc("create_task")
    @api.expect(createTask, validate=True)
    # @api.marshal_with(fetchTask)
    def post(self):
        data = api.payload

        # Safety: Validate the destination is permitted
        if data.get("target") not in current_app.config["OUTPUTS"]:
            return {
                "error": "This target is not valid. Please refer to Slurp's configuration."
            }, 400
        fmt_video = data.get("format_video", True)
        fmt_audio = data.get("format_audio", True)
        if not fmt_video and not fmt_audio:
            raise ValidationError(
                "Invalid format requested: you can't ask for nothing!"
            )
        fmt = Format.VIDEO_AUDIO
        if not fmt_video:
            fmt = Format.AUDIO_ONLY
        if not fmt_audio:
            fmt = Format.VIDEO_ONLY

        # Request that the fetch be worked on by the task queue.
        result = fetch.delay(
            url=data.get("url"),
            format=fmt,
            target=data.get("target"),
            slug=data.get("slug"),
        )
        return {"worker_id": result.id}, 201


@api.route("/worker/<string:worker_id>")
class Work(Resource):
    @api.doc("get_task_by_worker")
    @api.marshal_with(fetchTask)
    def get(self, worker_id):
        fetch = db.first_or_404(db.select(Fetch).filter_by(worker_id=worker_id))
        return fetch
