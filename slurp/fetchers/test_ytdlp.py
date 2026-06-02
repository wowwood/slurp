import httpx
import pytest
import yt_dlp.utils

from slurp import YTDLPFetcher
from slurp.fetchers.types import Format

_urls = {
    "small": "https://www.youtube.com/watch?v=eVrYbKBrI7o",  # toot
    "huge": "https://www.youtube.com/watch?v=mSX3OyW9Rao",  # 8 hours roaring fire
}


def __can_contact_youtube() -> bool:
    try:
        httpx.get("https://youtube.com")
    except (httpx.RequestError, httpx.ConnectError):
        return False
    return True


@pytest.mark.skipif(not __can_contact_youtube(), reason="Cannot contact YouTube")
@pytest.mark.xfail(
    raises=yt_dlp.utils.DownloadError,
    reason="Bot detection can cause these tests to fail",
)
class TestYTDLPFetcher:
    @pytest.fixture
    def fetcher_instance(self):
        return YTDLPFetcher()

    @pytest.mark.network
    def test_get_metadata(self, fetcher_instance):
        meta = fetcher_instance._get_metadata(_urls["huge"])
        assert meta is not None, "_get_metadata returned None"

    @pytest.mark.network
    @pytest.mark.dl
    def test_download(self, tmp_path, fetcher_instance):
        for event in fetcher_instance.fetch(
            _urls["small"], Format.VIDEO_AUDIO, str(tmp_path.absolute()), "test"
        ):
            print(event)
        assert (tmp_path / "test.webm").exists(), (
            "output file does not exist (expected 'test.webm')"
        )

    @pytest.mark.network
    @pytest.mark.dl
    @pytest.mark.huge_dl
    def test_huge_download(self, tmp_path, fetcher_instance):
        """
        Warning: this test downloads an enormous video with a huge filesize!
        It is intended purely as a stress test.
        """
        for event in fetcher_instance.fetch(
            _urls["huge"], Format.VIDEO_AUDIO, str(tmp_path.absolute()), "test"
        ):
            print(event)
        assert (tmp_path / "test.webm").exists(), (
            "output file does not exist (expected 'test.webm')"
        )
