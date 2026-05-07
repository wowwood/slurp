from flask_restx import Namespace, Resource, fields

from slurp.db import db
from slurp.models.task import FetchTask

api = Namespace("tasks", description="Fetch tasks")

# TODO
fetchTask = api.model(
    "FetchTask",
    {
        "id": fields.Integer(description="ID of task"),
        "ts_created": fields.DateTime(description="Created time"),
        "ts_updated": fields.DateTime(description="Last updated time"),
        "url": fields.String(description="URL that task fetches"),
        "slug": fields.String(description="Slug to save fetch as"),
        "format": fields.String(description="Download format"),
        "target": fields.String(description="Filesystem target identifier"),
        "status": fields.String(description="Task status"),
    },
)


@api.route("/")
class TaskList(Resource):
    @api.doc("list_tasks")
    @api.marshal_list_with(fetchTask)
    def get(self):
        db.session.execute(db.select(FetchTask)).fetchall()
