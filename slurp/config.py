"""
This module contains Slurp's default configuration.
If you make a change here, please update `config.template.toml` to match. Thanks!
"""


class DefaultConfig:
    # CSRF / Cookie signing key. Make this something random! See https://flask.palletsprojects.com/en/stable/config/#SECRET_KEY
    SECRET_KEY: str | None = None

    # URL to connect to your Redis instance at. THIS SHOULD HAVE PERSISTENCE CONFIGURED!
    REDIS_URL = "redis://localhost:6379/0"
    # REDIS_OM_URL = "oh_no"

    # Possible output directories. Strings will be split by the OS path separator (: on unix, ; on Windows)
    OUTPUTS: list | str | None = ["/tmp/slurp"]

    # Temporary storage directory.
    OUTPUT_TEMP: str | None = "/tmp/slurp_tmp"

    # Purger settings - The purger has two levels, PURGE and PRUNE.
    ## Purged events have their output file removed from the filesystem.
    ## Purge after this many hours:
    PURGE_AFTER: int = 24  # 1 day
    ## Pruned events have their logs expunged.
    ## Prune after this many hours:
    PRUNE_AFTER: int = 168  # 7 days

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
        "broker_url": REDIS_URL,
        "result_backend": REDIS_URL,
        "task_ignore_result": True,
    }
