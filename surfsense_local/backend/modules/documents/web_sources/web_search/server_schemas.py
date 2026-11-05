from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _server_address(url: str) -> str:
    """A server's base address: what `/search` is appended to."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("must be an http or https address")
    if parts.username or parts.password:
        raise ValueError("must not carry a user name or password")
    if parts.query or parts.fragment:
        raise ValueError("must not carry a query or a fragment")
    # urlsplit checks the port only when read; a bad one would fail every search.
    try:
        _ = parts.port
    except ValueError as error:
        raise ValueError(
            "must not carry a port that is not a number from 0 to 65535"
        ) from error
    # httpx sends the search and refuses hosts urlsplit takes, such as 192.168.1.256.
    try:
        httpx.URL(url)
    except httpx.InvalidURL as error:
        raise ValueError("must be an address a search can be sent to") from error
    return url.rstrip("/")


ServerAddress = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
    AfterValidator(_server_address),
]


class SearchServerRead(BaseModel):
    # None while searches go to SurfSense's server.
    url: str | None
    default_url: str


class SearchServerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None goes back to SurfSense's server.
    url: ServerAddress | None
