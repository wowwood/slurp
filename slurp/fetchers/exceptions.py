class FetcherMisconfiguredError(Exception):
    pass


class NoUpstreamMetadataError(Exception):
    pass


class AmbiguousQueryError(Exception):
    pass


class NoFetchersAvailable(Exception):
    pass


class FetchersExhaustedError(Exception):
    pass
