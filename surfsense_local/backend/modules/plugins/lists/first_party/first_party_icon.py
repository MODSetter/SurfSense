"""A first-party plugin's icon, packaged beside its list."""

from pathlib import Path

from modules.plugins.lists.first_party.first_party_list import (
    FIRST_PARTY_LIST,
    first_party_entries,
    icons_beside,
)


def first_party_icon(plugin_id: str) -> Path | None:
    """None for an id not listed, or an entry with no icon."""
    entry = next((e for e in first_party_entries() if e.id == plugin_id), None)
    if entry is None or entry.icon is None:
        return None
    return icons_beside(FIRST_PARTY_LIST) / entry.icon
