from . import create_app

flask_app = create_app()
celery = flask_app.extensions["celery"]
