"""Why a link could not be read; the pull turns each into the sentence the row shows."""

from enum import StrEnum


class Why(StrEnum):
    # No text to keep: a bot wall, a page only scripts build, an error page.
    UNREADABLE = "unreadable"
    GONE = "gone"
    # A file, such as a PDF, rather than a page.
    NOT_A_PAGE = "not_a_page"
    UNREACHABLE = "unreachable"
    # The site sent the read on to a host the user has not allowed.
    MOVED = "moved"
    NO_TRANSCRIPT = "no_transcript"
    VIDEO_UNAVAILABLE = "video_unavailable"
    # YouTube answered, but refused to share the transcript.
    REFUSED = "refused"


class ReadFailedError(Exception):
    def __init__(self, why: Why, host: str | None = None) -> None:
        super().__init__(f"{why}: {host}" if host else why)
        self.why = why
        # The host a MOVED read was sent on to.
        self.host = host
