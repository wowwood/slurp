import os

import httpx
import pytest

from slurp.lib.yt_block_check import YtBlockCheck

_urls = {
    "valid": [
        {
            "url": "https://www.youtube.com/watch?v=eVrYbKBrI7o",  # toot
            "output": "Video 'SKULL TRUMPET' by 'Big Purp' - Not a YouTube Partner - There are no reported country restrictions.",
        },
        {
            "url": "https://youtu.be/mSX3OyW9Rao",  # 8 hours roaring fire
            "output": "Video '🔥 Fireplace Evenings of Calm: Burning Logs, Crackling Sounds, and the Serenity of Pure Relaxation' by 'Fireplace 4K' - YouTube Partner - There are no reported country restrictions.",
        },
        # FIXME Please add some more tests for videos with licensing, restrictions, etc.
    ],
    "invalid": "https://youtu.be/1nv4l3d",
}


def __can_contact_youtube() -> bool:
    try:
        httpx.get("https://youtube.com")
    except (httpx.RequestError, httpx.ConnectError):
        return False
    return True


@pytest.mark.skipif(not __can_contact_youtube(), reason="Cannot contact YouTube")
@pytest.mark.skipif(
    os.environ.get("SLURP_EXT_API_YT_TOKEN", None) is None, reason="SLURP_EXT_API_YT_TO"
)
class TestYTBlockCheck:
    @pytest.fixture
    def fetcher_instance(self):
        return YtBlockCheck(api_key=os.environ["SLURP_EXT_API_YT_TOKEN"])

    @pytest.mark.network
    @pytest.mark.parametrize("url", _urls["valid"])
    def test_valid_videos(self, fetcher_instance, url: dict[str, str]):
        result = fetcher_instance.check(url["url"])
        assert result == url["output"]

    @pytest.mark.network
    def test_404_video(self, fetcher_instance):
        result = fetcher_instance.check(_urls["invalid"])
        assert (
            result
            == "The YouTube API reports that this video does not exist. Check the URL."
        )
