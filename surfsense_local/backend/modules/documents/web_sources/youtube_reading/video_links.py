"""The video a YouTube link names: `watch?v=`, `youtu.be`, `/shorts/`, `/embed/`, `/v/`, `/live/`."""

import re
from urllib.parse import SplitResult, parse_qs

# The one host a video is read from, whichever YouTube host its link names.
YOUTUBE_HOST = "www.youtube.com"
_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})
_VIDEO_PATH = re.compile(r"^/(?:shorts|embed|v|live)/([\w-]+)/?$")
# Every YouTube video id is eleven of these.
_ID = re.compile(r"^[\w-]{11}$")


def video_id(url: SplitResult) -> str | None:
    """None for a link that names no video, such as a channel or a playlist."""
    candidate = None
    if url.hostname == "youtu.be":
        candidate = url.path.strip("/")
    elif url.hostname in _HOSTS:
        if url.path.rstrip("/") == "/watch":
            candidate = next(iter(parse_qs(url.query).get("v", [])), None)
        elif match := _VIDEO_PATH.match(url.path):
            candidate = match[1]
    return candidate if candidate and _ID.match(candidate) else None
