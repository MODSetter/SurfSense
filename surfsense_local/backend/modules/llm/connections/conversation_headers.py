from urllib.parse import urlsplit
from uuid import uuid4

_CONSOLE_HOST = "opencode.ai"
_SESSION_PREFIX = "ses_"


def conversation_headers(url: str, conversation: str | None) -> dict[str, str]:
    """What this host requires to know about the caller and its conversation.

    OpenCode's Console: Go requires `x-opencode-session` on every request, so one
    outside any conversation is a session of its own, and clients name themselves.
    https://opencode.ai/docs/go https://opencode.ai/v2/docs/console/harnesses
    """
    if urlsplit(url).hostname != _CONSOLE_HOST:
        return {}
    session = conversation or uuid4().hex
    if not session.startswith(_SESSION_PREFIX):
        session = f"{_SESSION_PREFIX}{session}"
    return {"x-opencode-session": session, "User-Agent": "SurfSense"}
