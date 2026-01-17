"""
This module contains Slurp's default configuration.
If you make a change here, please update `config.template.toml` to match. Thanks!
"""


class DefaultConfig:
    # CSRF / Cookie signing key. Make this something random! See https://flask.palletsprojects.com/en/stable/config/#SECRET_KEY
    SECRET_KEY: str | None = None

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
