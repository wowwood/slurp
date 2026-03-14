import shutil
from typing import Generator

from slurp import FetcherMediaAvailable
from slurp.fetchers.types import FetcherUpdateEvent


def finalise(src: str, dest_dir: str) -> Generator[FetcherUpdateEvent]:
    yield FetcherMediaAvailable(_move_file(src, dest_dir))
    return


def _move_file(src: str, dest_dir: str) -> str:
    """
    move_file safely moves the source file into the given dest_dir.
    Done using an OS move command so that the OS filesystem properly locks / unlocks the target
    (which means any processing up the pipe from us doesn't start trying to read the file prematurely)

    :returns: Final absolute file path.
    """
    return shutil.move(src, dest_dir)
