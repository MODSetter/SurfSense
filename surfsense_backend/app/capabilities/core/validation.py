"""Shared Pydantic field types for capability I/O schemas."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

import validators
from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

_HTTP_SCHEMES = frozenset({"http", "https"})


def _validate_http_url(value: str) -> str:
    """Accept only well-formed http(s) URLs, returned trimmed and unchanged."""
    url = value.strip()
    if not validators.url(url) or urlsplit(url).scheme.lower() not in _HTTP_SCHEMES:
        raise PydanticCustomError("http_url", "must be a valid http(s) URL")
    return url


HttpUrlStr = Annotated[str, AfterValidator(_validate_http_url)]
"""A request URL validated as http(s) and kept as ``str`` (no normalization)."""
