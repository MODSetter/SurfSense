"""SurfSense's own plugins, packaged into the API and shown with no network or consent."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from modules.plugins.lists.icon_response import ICON_NAME
from modules.plugins.lists.list_entry import ListEntry
from modules.plugins.lists.plugin_host import PLUGIN_HOST, as_served

FIRST_PARTY_LIST = Path(__file__).with_name("plugins.json")


def icons_beside(path: Path) -> Path:
    """Icons live beside their list, as the registry's do."""
    return path.with_name("icons")


def checked_entries(path: Path) -> list[ListEntry]:
    """Every entry, or a ValueError naming the entry and the field that is wrong."""
    entries: list[ListEntry] = []
    # UTF-8 whatever the system's code page: Windows would read the list's curly
    # apostrophes as cp1252, and fail on a cp932 or cp936 system.
    for raw in json.loads(path.read_text(encoding="utf-8"))["plugins"]:
        name = raw.get("id", "?")
        try:
            entry = ListEntry.model_validate(raw)
        except ValidationError as error:
            raise ValueError(f"{name}: {error}") from error
        if entry.verification is not None:
            raise ValueError(
                f"{name}: verification is the registry's; the first-party list has none"
            )
        if entry.auth.type == "license" and not entry.url.startswith(f"{PLUGIN_HOST}/"):
            raise ValueError(
                f"{name}: url must be on {PLUGIN_HOST} to carry the license key"
            )
        if entry.about is None:
            raise ValueError(f"{name}: about must say what the plugin does")
        if not entry.tools:
            raise ValueError(f"{name}: tools must list what the server offers")
        if entry.added is None:
            raise ValueError(f"{name}: added must give the month it joined the list")
        if entry.icon is not None and not (
            ICON_NAME.match(entry.icon) and (icons_beside(path) / entry.icon).is_file()
        ):
            raise ValueError(f"{name}: icon {entry.icon} is not a file in icons/")
        if any(entry.id == seen.id for seen in entries):
            raise ValueError(f"{name}: listed twice")
        entries.append(entry)
    return entries


def first_party_entries() -> list[ListEntry]:
    """As this build reaches them: a developer's local plugin host stands in for SurfSense's."""
    return [
        entry.model_copy(
            update={
                "url": as_served(entry.url),
                "hosts": [_host(as_served(f"https://{host}")) for host in entry.hosts],
            }
        )
        for entry in checked_entries(FIRST_PARTY_LIST)
    ]


def _host(url: str) -> str:
    return urlsplit(url).hostname or ""
