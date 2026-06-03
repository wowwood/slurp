import shutil
from typing import Generator
from urllib.parse import SplitResult, urlsplit

from flask import current_app
from httpx import HTTPError
from pymediainfo import MediaInfo

from slurp.fetchers.types import (
    FetcherMediaAvailable,
    FetcherProgressReport,
    FetcherUpdateEvent,
)
from slurp.lib.yt_block_check import InvalidUrlException, YtBlockCheck, hostSuffixes
from slurp.models import Fetch

_acceptable_frame_rates = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]


def troubleshooter(fetch: Fetch) -> Generator[FetcherUpdateEvent]:
    """
    The Troubleshooter attempts to figure out why a given fetch failed.
    :param fetch: The fetch that failed.
    """
    # This canary is flipped if one or more of the troubleshooting routines are run.
    ts_run = False
    # If it's a YouTube video, we can hopefully provide some context.

    url_split: SplitResult = urlsplit(fetch.url)
    if len([i for i in hostSuffixes if i in url_split.netloc]) != 0:
        # This is a YouTube video - do ytBlockCheck
        ts_run = True
        if current_app.config.get("EXT_API_YT_TOKEN", None) is not None:
            try:
                result = YtBlockCheck(
                    api_key=current_app.config.get("YT_API_KEY")
                ).check(fetch.url)
                yield FetcherProgressReport(
                    typ="log",
                    level="info",
                    message=f"YouTube interrogation: {result}",
                )
            except InvalidUrlException as e:
                yield FetcherProgressReport(
                    typ="log",
                    level="warning",
                    message=f"YouTube interrogation failed; the URL appears malformed - {e}",
                )
            except HTTPError as e:
                yield FetcherProgressReport(
                    typ="log",
                    level="error",
                    message=f"Failed to communicate with YouTube API - {e}",
                )
        else:
            yield FetcherProgressReport(
                typ="log",
                level="warning",
                message="Unable to interrogate YouTube for troubleshooting information, as the YT_API_KEY configuration value has not been set.",
            )
    if not ts_run:
        yield FetcherProgressReport(
            typ="log",
            level="info",
            message="Unable to troubleshoot why the fetch failed. This is likely because the origin is not supported by the troubleshooter. Read the logs for more context.",
        )
    return


def finalise(src: str, dest_dir: str):
    problems = _validate_media_integrity(src)
    if len(problems) > 0:
        for problem in problems:
            yield FetcherProgressReport(
                typ="log",
                level="warning",
                message=f"Media problem: {problem}",
            )
    else:
        yield FetcherProgressReport(
            typ="log",
            level="info",
            message="Media seems fine",
        )
    yield FetcherMediaAvailable(_move_file(src, dest_dir))
    return


def _validate_media_integrity(media: str) -> list[str]:
    problems: list[str] = []
    media_info = MediaInfo.parse(media)
    for track in media_info.video_tracks:
        # Validate that the track is a continuous frame rate.
        if track.frame_rate_mode == "VFR":
            problems.append(f"Track {track.track_id} has a variable frame rate")

        # Validate that the frame rate is something reasonably reasonable.
        try:
            frame_rate = float(track.frame_rate)
            if frame_rate is not None and frame_rate not in _acceptable_frame_rates:
                problems.append(
                    f"Track {track.track_id} has a non-standard frame rate of {track.frame_rate}"
                )
        except ValueError:
            continue

    return problems


def _move_file(src: str, dest_dir: str) -> str:
    """
    move_file safely moves the source file into the given dest_dir.
    Done using an OS move command so that the OS filesystem properly locks / unlocks the target
    (which means any processing up the pipe from us doesn't start trying to read the file prematurely)

    :returns: Final absolute file path.
    """
    return shutil.move(src, dest_dir)
