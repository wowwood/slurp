from flask import current_app

from slurp.fetchers.cobalt import CobaltFetcher
from slurp.fetchers.types import Fetcher

from slurp.fetchers.ytdlp import YTDLPFetcher


def determine_fetcher(url: str):
    if any(elem in url for elem in YTDLPFetcher.service_urls):
        return YTDLPFetcher()

    # Everything else goes to Cobalt.
    # Done in a kinda yucky way - sue me.
    return CobaltFetcher(current_app.config.get("COBALT_URL"))


# Filled by configuration routine.
fetchers: list[Fetcher] = []