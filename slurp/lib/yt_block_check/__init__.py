from urllib.parse import SplitResult, parse_qs, urlsplit

import httpx

from .consts import api, country_codes, hostSuffixes
from .exceptions import InvalidUrlException


class YtBlockCheck:
    __api_key: str | None = None

    def __init__(self, api_key: str) -> None:
        self.__api_key = api_key

    def check(self, url: str) -> str:
        """
        check performs basic checks for the availability and block status of a given YouTube video.
        :param url: URL of the video.
        :return: A human-readable string describing the video, its block status, etc.
        """
        # Break the URL apart.
        url_split: SplitResult = urlsplit(url)
        if len([i for i in hostSuffixes if i in url_split.netloc]) == 0:
            raise InvalidUrlException("not a YouTube URL")

        # Get the video ID out of the URL
        video_id: str | None = None
        if "youtube.com" in url_split.netloc:
            # Classic / long URL - parse the query string
            if not url_split.path.startswith("/watch"):
                raise InvalidUrlException("not a watch URL")
            query = parse_qs(url_split.query)
            if query is None or query.get("v", None) is None:
                raise InvalidUrlException("URL does not include query string")

            video_id = query["v"]
            assert video_id is not list, "multiple video query elements in URL"
        else:
            if url_split.path == "/":
                raise InvalidUrlException("not a watch URL")
            video_id = url_split.path.split("/")[1]

        # Build the query
        params = {
            "part": "snippet,contentDetails",
            "id": video_id,
            "key": self.__api_key,
        }
        response_data = httpx.get(api, params=params).raise_for_status().json()

        r_page_info = response_data.get("pageInfo")
        assert r_page_info is not None, "invalid response from YouTube API"
        assert r_page_info.get("totalResults", None) is not None, (
            "invalid response from YouTube API"
        )

        if r_page_info.get("totalResults") == 0:
            return (
                "The YouTube API reports that this video does not exist. Check the URL."
            )

        assert (
            response_data.get("items", None) is not None
            and len(response_data.get("items")) != 0
        ), "invalid response from YouTube API - no items"

        vid_obj = response_data["items"][0]
        vid_content_details = vid_obj.get("contentDetails", {})
        vid_meta_obj = vid_obj["snippet"]
        # vid_id = vid_obj["id"]
        vid_title = vid_meta_obj["title"]
        vid_author = vid_meta_obj["channelTitle"]
        # vid_author_channel_id = vid_meta_obj["channelId"]
        vid_is_licensed = vid_content_details["licensedContent"]
        vid_restriction = vid_content_details.get("regionRestriction", None)
        vid_is_restricted = True if vid_restriction is not None else False

        # Build the description string
        result = (
            f"Video '{vid_title}' by '{vid_author}' - "
            f"{'YouTube Partner' if vid_is_licensed else 'Not a YouTube Partner'} - "
        )
        if vid_is_restricted:
            restricted_countries = [
                i for i in country_codes if i not in vid_restriction
            ]
            result += f"Allowed countries: {','.join(vid_restriction)}"
            result += f"Restricted countries: {','.join(restricted_countries)}"
        else:
            result += "There are no reported country restrictions."
        return result
