"""A video's transcript and facts, read from www.youtube.com on the user's own connection.

youtube-transcript-api reads the watch page, YouTube's player answer, then the
track, all on www.youtube.com. Its session refuses any other host, so a change in
the library or at YouTube can never reach a host the user was not asked about.
"""

from contextlib import suppress
from typing import Any
from urllib.parse import urlsplit

import requests
from youtube_transcript_api import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    FetchedTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    Transcript,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApi,
)

from modules.documents.web_sources.pullers.puller import HostCheck, Pulled
from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why
from modules.documents.web_sources.source_text.source_markdown import (
    source_markdown,
)
from modules.documents.web_sources.youtube_reading.transcript_tracks import (
    chosen_track,
)
from modules.documents.web_sources.youtube_reading.video_links import (
    YOUTUBE_HOST,
    video_id,
)

# The library sends without a timeout, and a stalled connection would hold the
# worker's thread with no cancel reaching it.
TIMEOUT = (10, 30)
# Its answer carries the video's title, channel and description.
_PLAYER_PATH = "/youtubei/v1/player"


class _OtherHostError(requests.RequestException):
    """The library asked for a host the user was not asked about."""


class _YouTubeOnly(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.details: dict[str, Any] = {}
        self.hooks["response"].append(self._keep_details)

    def request(self, method: str | bytes, url: str | bytes, **kwargs: Any):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = TIMEOUT
        return super().request(method, url, **kwargs)

    def send(self, request: requests.PreparedRequest, **kwargs: Any):
        # Every hop, redirects included, passes here.
        if urlsplit(request.url or "").hostname != YOUTUBE_HOST:
            raise _OtherHostError(request.url)
        return super().send(request, **kwargs)

    def _keep_details(self, response: requests.Response, *_: Any, **__: Any) -> None:
        if response.ok and urlsplit(response.url).path == _PLAYER_PATH:
            with suppress(ValueError, AttributeError):
                self.details = response.json().get("videoDetails") or {}


def read_video(url: str, reach: HostCheck) -> Pulled:
    reach(YOUTUBE_HOST)
    video = video_id(urlsplit(url))
    if video is None:
        raise ReadFailedError(Why.UNREADABLE)
    with _YouTubeOnly() as session:
        track, fetched = _transcript(session, video)
        details = session.details
    text = _lines(fetched)
    if not text:
        raise ReadFailedError(Why.NO_TRANSCRIPT)
    title = details.get("title") or url
    markdown = source_markdown(
        title,
        [
            ("Channel", details.get("author")),
            ("Duration", _duration(details.get("lengthSeconds"))),
            ("Link", url),
            ("Transcript", track.language),
        ],
        [("Description", details.get("shortDescription")), ("Transcript", text)],
    )
    return Pulled(title, markdown)


def _transcript(
    session: requests.Session, video: str
) -> tuple[Transcript, FetchedTranscript]:
    try:
        track = chosen_track(YouTubeTranscriptApi(http_client=session).list(video))
        if track is None:
            raise ReadFailedError(Why.NO_TRANSCRIPT)
        return track, track.fetch()
    except (TranscriptsDisabled, NoTranscriptFound) as error:
        raise ReadFailedError(Why.NO_TRANSCRIPT) from error
    except (VideoUnavailable, InvalidVideoId, VideoUnplayable, AgeRestricted) as error:
        raise ReadFailedError(Why.VIDEO_UNAVAILABLE) from error
    except (CouldNotRetrieveTranscript, _OtherHostError) as error:
        # A bot check, a token YouTube now asks for, an answer that changed shape.
        raise ReadFailedError(Why.REFUSED) from error
    except requests.RequestException as error:
        raise ReadFailedError(Why.UNREACHABLE) from error


def _lines(fetched: FetchedTranscript) -> str:
    """A caption per line; generated tracks roll a caption into the next cue."""
    lines: list[str] = []
    for snippet in fetched:
        line = " ".join(snippet.text.split())
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


def _duration(seconds: object) -> str | None:
    """`1:02:03`, or `4:05` under an hour."""
    try:
        total = int(str(seconds))
    except ValueError:
        return None
    if total <= 0:
        return None
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"
