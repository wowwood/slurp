from slurp.fetchers.types import Fetcher


def fetchers_for_url(url: str) -> list[Fetcher]:
    valid_fetchers: list[Fetcher] = []
    # Loop through all filters that are ready to handle requests.
    for fetcher in sorted(
        filter(lambda f: f.ready, fetchers), key=lambda f: f.priority
    ):
        if fetcher.service_urls is None:
            # Can fetch any URL
            valid_fetchers.append(fetcher)
            continue
        if any(elem in url for elem in fetcher.service_urls):
            valid_fetchers.append(fetcher)
    return valid_fetchers


# Filled by configuration routine.
fetchers: list[Fetcher] = []
