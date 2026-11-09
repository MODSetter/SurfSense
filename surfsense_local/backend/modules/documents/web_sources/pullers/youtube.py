"""A YouTube video's link: its transcript, read from www.youtube.com.

Any other YouTube link, such as a channel or a playlist, is read as a page.
"""

from urllib.parse import SplitResult

from modules.documents.web_sources.pullers.puller import HostCheck, Pulled, Puller
from modules.documents.web_sources.youtube_reading.video_links import (
    YOUTUBE_HOST,
    video_id,
)


def _takes(url: SplitResult) -> bool:
    return video_id(url) is not None


def _hosts(_: str) -> list[str]:
    """youtu.be and m.youtube.com links too: only the video's id is sent, to one host."""
    return [YOUTUBE_HOST]


def _read(url: str, reach: HostCheck) -> Pulled:
    # Imported where a read runs, the plugins worker, as the page reader is.
    from modules.documents.web_sources.youtube_reading.video_read import read_video

    return read_video(url, reach)


PULLER = Puller(id="youtube", takes=_takes, hosts=_hosts, read=_read)
