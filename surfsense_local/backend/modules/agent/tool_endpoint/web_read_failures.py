"""Why a page or a video could not be read, told to the agent so it can say so or go on."""

from modules.documents.web_sources.pullers.read_failure import ReadFailedError, Why

_SENTENCES = {
    Why.UNREADABLE: (
        "This page could not be read without a browser: it may need a login, run "
        "on scripts, or show a check only a person passes. The user can open it, "
        "save it as a PDF and add the file to their sources."
    ),
    Why.GONE: "This page no longer exists at this link.",
    Why.NOT_A_PAGE: (
        "This link is a file, not a web page. The user can download it and add "
        "the file to their sources."
    ),
    Why.UNREACHABLE: "The site could not be reached. Try again later.",
    Why.NO_TRANSCRIPT: "This video has no captions, so it has no transcript.",
    Why.VIDEO_UNAVAILABLE: (
        "This video cannot be read: it may be private, removed or age-restricted."
    ),
    Why.REFUSED: "YouTube refused to share this video's transcript. Try again later.",
}


def read_failure_text(error: ReadFailedError) -> str:
    if error.why is Why.MOVED:
        return f"The page moved to {error.host}. Try again to read it there."
    return _SENTENCES[error.why]
