import ast
import os
import tomllib

from celery import Celery, Task
from flask import Flask
from flask_sse import sse

from slurp.api import api_blueprint
from slurp.db import bind_redis
from slurp.fetchers import (
    fetchers,
)
from slurp.fetchers.cobalt import CobaltFetcher
from slurp.fetchers.exceptions import FetcherMisconfiguredError
from slurp.fetchers.get_iplayer import BBCiPlayerFetcher
from slurp.fetchers.ytdlp import YTDLPFetcher
from slurp.helpers import format_duration
from slurp.routes import main_blueprint


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

    app.register_blueprint(sse, url_prefix="/api/v1/stream")

    app.register_blueprint(main_blueprint)

    app.register_blueprint(api_blueprint)

    return app


def serve():
    create_app().run(host="0.0.0.0", port=8000, debug=False)
