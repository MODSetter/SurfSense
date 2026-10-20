"""The headers a request gives, checked before anything is contacted."""

from fastapi import HTTPException, status

from modules.plugins.remote.sign_in.headers.header_rules import (
    SignInHeader,
    header_problem,
)
from modules.plugins.remote.sign_in.headers.headers_credential import bearer


def given_headers(
    headers: list[SignInHeader] | None, token: str | None = None
) -> list[SignInHeader] | None:
    """None when none were given; a bare key is sent as `Authorization: Bearer`."""
    given = headers if headers else bearer(token) if token else None
    if given is None:
        return None
    problem = header_problem(given)
    if problem is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "plugin_header_not_allowed", "message": problem},
        )
    return given


def as_sent(headers: list[SignInHeader] | None) -> dict[str, str]:
    return {h.name.strip(): h.value for h in headers or []}
