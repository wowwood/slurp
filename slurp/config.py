"""
This module contains Slurp's default configuration.
If you make a change here, please update `config.template.toml` to match. Thanks!
"""


class DefaultConfig:
    # CSRF / Cookie signing key. Make this something random! See https://flask.palletsprojects.com/en/stable/config/#SECRET_KEY
    SECRET_KEY: str | None = None

    # Database storage location. This should probably be 'sqlite:///[something]'.
    SQLALCHEMY_DATABASE_URI: str = "sqlite:////tmp/slurp/database.db"
    # Storage location for the Celery result backend. This should probably be next door to your main database.
    CELERY_SQLALCHEMY_DATABASE_URI: str = "sqlite:////tmp/slurp/celery.db"
    # Location to connect to the message queue at. The default presumes you have a RabbitMQ instance available at the default location.
    BROKER_URL: str = "amqp://localhost:5672"

    # Possible output directories. Strings will be split by the OS path separator (: on unix, ; on Windows)
    OUTPUTS: list | str | None = ["/tmp/slurp"]

    # Enable the YTDLP fetcher.
    FETCHER_YTDLP_ENABLED: bool = True

    # Enable the get_iplayer fetcher.
    # Note: get_iplayer must be installed separately (we just call the binary).
    FETCHER_BBC_IPLAYER_ENABLED: bool = False

    # Cobalt fetcher settings.
    # Note: you must have a valid Cobalt instance to run queries against. See the README for more information.

    # Enable the Cobalt fetcher.
    FETCHER_COBALT_ENABLED: bool = False
    # Cobalt instance URL (with trailing slash).
    FETCHER_COBALT_URL: str = "http://localhost:9000/"
    # OPTIONAL: Cobalt API Key. Omit to use unauthenticated connection (make sure your instance is firewalled correctly!)
    FETCHER_COBALT_KEY: str = ""

    CELERY: dict = {
        # Message queue.
        "broker_url": BROKER_URL,
        "result_backend": f"db+{CELERY_SQLALCHEMY_DATABASE_URI}",
    }
