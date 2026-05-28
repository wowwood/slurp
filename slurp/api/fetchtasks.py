from enum import Enum
from typing import Annotated, Any, Type

from flask import current_app, request
from flask_restx import Namespace, Resource, ValidationError, fields
from pydantic import BaseModel, BeforeValidator, Field, field_serializer

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
        "id": fields.String(attribute="pk", description="ID of task"),
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


def accept_enum_name(enum: Type[Enum]) -> BeforeValidator:
    """ "
    Pydantic validator that validates against the name of the enum value, not the value itself.
    See https://github.com/pydantic/pydantic/discussions/2980#discussioncomment-15042101
    """

    def validator(value: Any) -> Any:
        if isinstance(value, str) and value in enum.__members__:
            return enum[value]
        else:
            return value

    return BeforeValidator(validator)


class createTaskSchema(BaseModel):
    url: str = Field(description="URL that should be fetched")
    format: Annotated[Format | None, accept_enum_name(Format)] = Field(
        description="Download format"
    )

    @field_serializer("format")
    def serialize_format(self, format: Format) -> str:
        return format.name

    slug: str = Field(description="Slug to save fetch as")
    target: str = Field(
        description="Filesystem target identifier. This MUST be a valid destination as configured."
    )


@api.route("/")
class List(Resource):
    @api.doc("list_tasks")
    @api.marshal_list_with(fetchTask)
    def get(self):
        fetches = Fetch.find().all()
        return fetches

    @api.doc("create_task")
    # @api.marshal_with(fetchTask)
    def post(self):
        try:
            # Handle JSON
            if request.is_json:
                raw_data = request.get_json()

            # Handle form-data / x-www-form-urlencoded
            else:
                raw_data = request.form.to_dict()

            # Validate with Pydantic
            data = createTaskSchema(**raw_data)

            # Safety: Validate the destination is permitted
            if data.target not in current_app.config["OUTPUTS"]:
                return {
                    "error": "This target is not valid. Please refer to Slurp's configuration."
                }, 400

            # Request that the fetch be worked on by the task queue.
            result = fetch.delay(
                url=data.url,
                format=data.format,
                target=data.target,
                slug=data.slug,
            )
            return {"worker_id": result.id}, 201
            # return {"message": "Task created", "data": data.model_dump()}, 200

        except ValidationError as e:
            return {"message": "Validation failed", "errors": e}, 400


@api.route("/worker/<string:worker_id>")
class Work(Resource):
    @api.doc("get_task_by_worker")
    @api.marshal_with(fetchTask)
    def get(self, worker_id):
        fetch = Fetch.find(worker_id == worker_id).first()
        return fetch
