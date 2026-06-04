import os
import tomllib

from celery import Celery, Task
from flask import Flask
from flask_sse import sse

from slurp.api import api_blueprint
from slurp.db import bind_redis
from slurp.fetchers import fetcher_manager
from slurp.helpers import format_duration
from slurp.routes import main_blueprint
from slurp.tasks import _init_periodic_tasks


def __celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(
        app.name,
        task_cls=FlaskTask,
        broker=app.config["REDIS_URL"],
        result_backend=app.config["REDIS_URL"],
    )
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app

    # Create task routes
    celery_app.conf.task_routes = {
        # Fetch tasks should take place in their own queue, as they can be quite lengthy.
        "slurp.fetch": {"queue": "fetch"}
    }

    # Bind periodic tasks
    celery_app.on_after_configure.connect(_init_periodic_tasks)
    return celery_app


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

    # Bind Celery
    __celery_init_app(app)

    # Bind Redis
    bind_redis(app)

    if isinstance(app.config["OUTPUTS"], str):
        app.logger.debug(f"Outputs pre-split: {app.config['OUTPUTS']}")
        # Normalise the OUTPUTS list to a list
        app.config["OUTPUTS"] = app.config.get("OUTPUTS", "").split(os.pathsep)
        app.logger.info(f"Configured outputs: {','.join(app.config['OUTPUTS'])}")

    fetcher_manager.init_app(app)

    app.logger.info(
        f"The following fetchers are enabled: [{', '.join([f.name for f in app.extensions['fetchers'].get_all()])}]"
    )

    app.jinja_env.filters["duration"] = format_duration

    app.register_blueprint(sse, url_prefix="/api/v1/stream")

    app.register_blueprint(main_blueprint)

    app.register_blueprint(api_blueprint)

    return app


def serve():
    create_app().run(host="0.0.0.0", port=8000, debug=False)
