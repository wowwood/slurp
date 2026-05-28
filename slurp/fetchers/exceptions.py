class FetcherMisconfiguredError(Exception):
    pass


class NoUpstreamMetadataError(Exception):
    pass


class AmbiguousQueryError(Exception):
    pass


class NoFetchersAvailable(Exception):
    def __str__(self):
        return "No configured fetchers are available"


class FetchersExhaustedError(Exception):
    def __str__(self):
        return "Available Fetchers exhausted"
