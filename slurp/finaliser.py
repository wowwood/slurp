import shutil
from typing import Generator

from pymediainfo import MediaInfo

from slurp import FetcherMediaAvailable, FetcherProgressReport
from slurp.fetchers.types import FetcherUpdateEvent

_acceptable_frame_rates = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]


def finalise(src: str, dest_dir: str) -> Generator[FetcherUpdateEvent]:
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
