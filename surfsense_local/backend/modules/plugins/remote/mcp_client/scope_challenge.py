"""The scopes a `403 insufficient_scope` asks for, read from its `WWW-Authenticate` challenge.

The spec has the client treat the challenge's scopes as authoritative and sign in again.
"""

import re

import httpx2

_ERROR = re.compile(r'error="?insufficient_scope"?', re.IGNORECASE)
_SCOPE = re.compile(r'scope="([^"]*)"', re.IGNORECASE)


def challenged_scopes(response: httpx2.Response) -> list[str] | None:
    """None unless this is a 403 naming the scopes it wants."""
    if response.status_code != 403:
        return None
    challenge = response.headers.get("www-authenticate", "")
    if not _ERROR.search(challenge):
        return None
    found = _SCOPE.search(challenge)
    scopes = found.group(1).split() if found else []
    return scopes or None
