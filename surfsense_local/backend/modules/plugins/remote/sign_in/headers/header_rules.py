"""Which headers a user may give a plugin's server: a key in any header, never the transport's own."""

import re

from pydantic import BaseModel

MOST_HEADERS = 10
LONGEST_NAME = 64
LONGEST_VALUE = 4096
# An HTTP token (RFC 9110): no space, colon or control character.
_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
# The transport sets these, and a server trusts them; one given here would replace them.
REFUSED_NAMES = {
    "host",
    "content-length",
    "content-type",
    "accept",
    "connection",
    "transfer-encoding",
    "cookie",
    "mcp-session-id",
    "mcp-protocol-version",
    "last-event-id",
}


class SignInHeader(BaseModel):
    name: str
    value: str


def header_problem(headers: list[SignInHeader]) -> str | None:
    """A sentence naming the first header refused, or None. Never quotes a value."""
    if not headers:
        return "Give at least one header."
    if len(headers) > MOST_HEADERS:
        return f"A plugin takes at most {MOST_HEADERS} headers."
    seen: set[str] = set()
    for header in headers:
        name = header.name.strip()
        if not (_NAME.match(name) and len(name) <= LONGEST_NAME):
            return f"{name or 'A header'} is not a header name."
        if name.lower() in REFUSED_NAMES:
            return f"{name} is set by SurfSense itself."
        if name.lower() in seen:
            return f"{name} is given twice."
        seen.add(name.lower())
        value = header.value
        if not value.strip():
            return f"{name} needs a value."
        if len(value) > LONGEST_VALUE or any(c in value for c in "\r\n\0"):
            return f"{name}'s value is too long or holds a line break."
    return None
