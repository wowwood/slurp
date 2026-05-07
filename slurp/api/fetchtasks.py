# from flask.views import MethodView
# from flask_smorest import Blueprint
from flask_restx import Namespace, Resource, fields
from sqlmodel import Session, select

from slurp.db import engine
from slurp.models.task import FetchTask

# tasks_blueprint = Blueprint(
#     "tasks", "tasks", url_prefix="/tasks", description="Operations on Tasks"
# )


# @tasks_blueprint.route("/")
# class Tasks(MethodView):
#     @tasks_blueprint.response(200, FetchTask)
#     def get(self):
#         with Session(engine) as session:
#             statement = select(FetchTask)
#             if id is not None:
#                 return session.exec(statement.where(FetchTask.id == id)).first()
#             else:
#                 return session.exec(statement).all()
#
#
# @tasks_blueprint.route("/<task_id>")
# class TasksById(MethodView):
#     @tasks_blueprint.response(200, FetchTask)
#     def get(self, task_id):
#         """Get Task by ID"""
#         with Session(engine) as session:
#             return session.get(FetchTask, task_id)

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
        with Session(engine) as session:
            return session.exec(select(FetchTask)).all()
