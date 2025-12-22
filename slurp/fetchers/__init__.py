from slurp.fetchers.types import Format

from slurp.fetchers.ytdlp import YTDLPFetcher


def determine_fetcher(url: str):
    if any(elem in url for elem in ["youtu.be", "youtube.com"]):
        return YTDLPFetcher()

    raise ValueError("unsupported service")


