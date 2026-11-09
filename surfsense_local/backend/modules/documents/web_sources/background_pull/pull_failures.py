"""Why a pull failed, in a sentence the sources panel shows on the row."""

from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why
from modules.egress.service import EgressDeniedError

# A browser gets past what this reader cannot, and SurfSense reads the PDF it prints.
UNREADABLE = (
    "This page couldn't be read. Open it in your browser, save it as a PDF, "
    "and add the file instead."
)
_SENTENCES = {
    Why.UNREADABLE: UNREADABLE,
    Why.GONE: "This page no longer exists at this link.",
    Why.NOT_A_PAGE: (
        "This link is a file, not a web page. Download it and add the file instead."
    ),
    Why.UNREACHABLE: "This link couldn't be reached. Check your connection and retry.",
    Why.NO_TRANSCRIPT: "This video has no captions, so there is no transcript to add.",
    Why.VIDEO_UNAVAILABLE: (
        "This video can't be read: it may be private, removed or age-restricted."
    ),
    Why.REFUSED: "YouTube didn't share this video's transcript. Try again later.",
}


def read_sentence(error: ReadFailedError) -> str:
    if error.why is Why.MOVED:
        return f"This page moved to {error.host}. Retry to allow reading it there."
    return _SENTENCES[error.why]


def network_sentence(error: EgressDeniedError) -> str:
    return f"Sending to {error.host} is off in Settings > Network."
