import httpx
import pytest

from slurp import BBCiPlayerFetcher
from slurp.fetchers.exceptions import FetcherMisconfiguredError, NoUpstreamMetadataError

_urls = {
    "valid_tv": [
        "https://www.bbc.co.uk/iplayer/episode/p0hbq90v",  # Dog
        "https://www.bbc.co.uk/programmes/p0mnrc9d",  # House of the Year
    ],
    "valid_sounds": [
        "https://www.bbc.co.uk/sounds/play/m002909c",  # Lawn Mowers
    ],
    "tv_series": "https://www.bbc.co.uk/iplayer/episodes/p0db9b2t/",  # The Traitors
    "invalid_wrong_tld": "https://www.youtube.com",  # post-charter review BBC
    "invalid_does_not_exist": "https://www.bbc.co.uk/iplayer/episode/p0hbqdf2/",  # garbage ID
}


def __command_available() -> bool:
    fetcher = BBCiPlayerFetcher()
    try:
        if not fetcher.ready:
            return False
    except FetcherMisconfiguredError:
        return False
    return True


def __can_contact_iplayer() -> bool:
    try:
        httpx.get("https://www.bbc.co.uk/iplayer")
    except (httpx.RequestError, httpx.ConnectError):
        return False
    return True


@pytest.mark.skipif(not __can_contact_iplayer(), reason="Cannot contact BBC iPlayer")
@pytest.mark.skipif(not __command_available(), reason="No BBC iPlayer")
class TestBBCiPlayerFetcher:
    @pytest.fixture
    def fetcher_instance(self):
        return BBCiPlayerFetcher()

    @pytest.mark.network
    @pytest.mark.parametrize("url", _urls["valid_tv"])
    def test_get_metadata_valid_tv(self, fetcher_instance, url):
        meta = fetcher_instance._get_metadata(url)
        assert meta is not None, "_get_metadata returned None"
        assert meta.format == "tv", (
            f"_get_metadata returned an unexpected format - expected tv got {meta.format}"
        )

    @pytest.mark.network
    @pytest.mark.parametrize("url", _urls["valid_sounds"])
    def test_get_metadata_valid_sounds(self, fetcher_instance, url):
        if not fetcher_instance.ready:
            pytest.skip("get_iplayer not available to run test")

        meta = fetcher_instance._get_metadata(url)
        assert meta is not None, "_get_metadata returned None"
        assert meta.format == "radio", (
            f"_get_metadata returned an unexpected format - expected radio got {meta.format}"
        )

    @pytest.mark.network
    def test_get_metadata_invalid(self, fetcher_instance):
        if not fetcher_instance.ready:
            pytest.skip("get_iplayer not available to run test")

        # Test invalid TLD
        with pytest.raises(NoUpstreamMetadataError):
            fetcher_instance._get_metadata(_urls["invalid_wrong_tld"])

        # Test invalid show ID
        with pytest.raises(NoUpstreamMetadataError):
            fetcher_instance._get_metadata(_urls["invalid_does_not_exist"])
            pytest.fail()

    @pytest.mark.network
    def test_get_metadata_series(self, fetcher_instance):
        if not fetcher_instance.ready:
            pytest.skip("get_iplayer not available to run test")

        # Test series
        # At the moment get_iplayer just returns an invalid result if you do this.
        with pytest.raises(NoUpstreamMetadataError):
            fetcher_instance._get_metadata(_urls["tv_series"])
