from flask import Blueprint
from flask_restx import Api

from slurp.api.fetchtasks import api as fetchtasksNS

api_blueprint = Blueprint("api", __name__, url_prefix="/api/v1")

api = Api(
    api_blueprint,
    version="1.0",
    title="Slurp API",
    description="Slurp API",
)

api.add_namespace(fetchtasksNS)
