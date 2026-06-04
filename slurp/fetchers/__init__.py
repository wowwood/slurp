import ast
import shutil

from slurp.fetchers.cobalt import CobaltFetcher
from slurp.fetchers.exceptions import FetcherMisconfiguredError
from slurp.fetchers.get_iplayer import BBCiPlayerFetcher
from slurp.fetchers.types import Fetcher
from slurp.fetchers.ytdlp import YTDLPFetcher


# slurp/fetchers/__init__.py
class FetcherManager:
    def __init__(self):
        self.fetchers = []

    def init_app(self, app):
        """Initialize fetchers for this app instance."""
        self.fetchers = []  # Reset for this app

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
                # noinspection PyDeprecation
                path = shutil.which("deno")
                if path is None:
                    app.logger.warning(
                        "The YTDLP fetcher does not have a Javascript runtime configured, and 'deno' is not available on the system path."
                        "It will still function, but in a degraded state - please set one using the FETCHER_YTDLP_JS_RUNTIMES config flag."
                    )
            try:
                self.fetchers.append(
                    YTDLPFetcher(
                        js_runtimes=js_runtimes,
                    )
                )
            except FetcherMisconfiguredError as e:
                app.logger.error("Failed to initialize the YTDLP fetcher: %s", e)

        if app.config.get("FETCHER_COBALT_ENABLED") is True:
            try:
                self.fetchers.append(
                    CobaltFetcher(
                        app.config.get("FETCHER_COBALT_URL", "http://localhost:9000"),
                        app.config.get("FETCHER_COBALT_KEY", None),
                    )
                )
            except FetcherMisconfiguredError as e:
                app.logger.error("Failed to initialize the Cobalt fetcher: %s", e)

        if app.config.get("FETCHER_BBC_IPLAYER_ENABLED") is True:
            try:
                self.fetchers.append(BBCiPlayerFetcher())
            except FetcherMisconfiguredError as e:
                app.logger.error("Failed to initialize the get_iplayer fetcher: %s", e)

        if len(self.fetchers) == 0:
            raise RuntimeError("No fetchers enabled - please enable some!")

        app.extensions["fetchers"] = self

    def get_all(self):
        return self.fetchers

    def get_for_url(self, url: str) -> list[Fetcher]:
        valid_fetchers: list[Fetcher] = []
        # Loop through all filters that are ready to handle requests.
        for fetcher in sorted(
            filter(lambda f: f.ready, self.fetchers), key=lambda f: f.priority
        ):
            if fetcher.service_urls is None:
                # Can fetch any URL
                valid_fetchers.append(fetcher)
                continue
            if any(elem in url for elem in fetcher.service_urls):
                valid_fetchers.append(fetcher)
        return valid_fetchers


fetcher_manager = FetcherManager()
