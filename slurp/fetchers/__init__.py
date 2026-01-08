from slurp.fetchers.cobalt import CobaltFetcher

from slurp.fetchers.ytdlp import YTDLPFetcher


def determine_fetcher(url: str):
    if any(elem in url for elem in ["youtu.be", "youtube.com"]):
        return YTDLPFetcher()

    if any(elem in url for elem in ["streamable.com"]):
        return CobaltFetcher()

    raise ValueError("unsupported service")


