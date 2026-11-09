"""The headers a registry entry names, filled with the values the user typed.

Values go only in headers the reviewed entry names, each with the prefix it gives.
"""

from fastapi import HTTPException, status

from modules.plugins.lists.list_entry import EntryHeader
from modules.plugins.remote.sign_in.headers.given_headers import given_headers
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader


def filled_headers(
    named: list[EntryHeader], typed: list[SignInHeader] | None
) -> list[SignInHeader]:
    values = {h.name.strip().lower(): h.value for h in typed or []}
    expected = {h.name.lower() for h in named}
    for name in values:
        if name not in expected:
            _refuse(f"{name} is not a header this plugin takes.")
    missing = [h.name for h in named if not values.get(h.name.lower())]
    if missing:
        _refuse(f"{missing[0]} needs a value.")
    filled = [
        SignInHeader(name=h.name, value=f"{h.prefix or ''}{values[h.name.lower()]}")
        for h in named
    ]
    return given_headers(filled) or []


def _refuse(message: str) -> None:
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {"code": "plugin_header_not_allowed", "message": message},
    )
