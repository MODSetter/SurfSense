"""A list entry's icon as the screen loads it, from either list.

An SVG can carry script, so it is served sandboxed and never sniffed as anything else.
"""

import re
from pathlib import Path

from fastapi import Response

# A plain file name, so a listed name can never reach outside the icons folder.
ICON_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\.(svg|png)$")
CONTENT_TYPES = {"svg": "image/svg+xml", "png": "image/png"}

_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-cache",
}


def icon_response(path: Path) -> Response:
    return Response(
        path.read_bytes(),
        media_type=CONTENT_TYPES[path.suffix.removeprefix(".")],
        headers=_HEADERS,
    )
