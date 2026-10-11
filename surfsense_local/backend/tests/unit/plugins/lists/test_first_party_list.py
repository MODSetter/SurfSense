import json
from pathlib import Path
from typing import Any

import pytest

from modules.plugins.lists.first_party.first_party_list import (
    FIRST_PARTY_LIST,
    checked_entries,
)

pytestmark = pytest.mark.unit


def scrapers(**changed: Any) -> dict[str, Any]:
    """A valid first-party entry, with `changed` fields replaced."""
    entry = {
        "id": "scrapers",
        "kind": "remote",
        "publisher": "surfsense",
        "name": "SurfSense Scrapers",
        "description": "Search the web and scrape sites.",
        "author": "SurfSense",
        "url": "https://plugins.surfsense.com/scrapers/mcp",
        "auth": {"type": "license"},
        "hosts": ["plugins.surfsense.com"],
        "access": "license",
    }
    return {**entry, **changed}


def listed(tmp_path: Path, *entries: dict[str, Any]) -> Path:
    """A first-party list file holding `entries`."""
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"schema_version": 1, "plugins": list(entries)}))
    return path


def test_the_packaged_list_passes_its_check() -> None:
    """A bad entry fails CI here, not on a user's machine."""
    assert [entry.id for entry in checked_entries(FIRST_PARTY_LIST)] == ["scrapers"]


def test_a_newer_field_is_ignored(tmp_path: Path) -> None:
    """So a list written for a newer app does not break an older one."""
    entry = scrapers(rating=5)

    assert checked_entries(listed(tmp_path, entry))[0].id == "scrapers"


@pytest.mark.parametrize(
    ("changed", "field"),
    [
        ({"id": "Scrapers"}, "id"),
        ({"url": "http://plugins.surfsense.com/scrapers/mcp"}, "url"),
        ({"url": "https://key@plugins.surfsense.com/scrapers/mcp"}, "url"),
        ({"hosts": ["other.example"]}, "hosts"),
        ({"hosts": ["plugins.surfsense.com", "127.0.0.1"]}, "hosts"),
        ({"publisher": "partner"}, "publisher"),
        ({"access": "external"}, "access_note"),
        ({"name": ""}, "name"),
    ],
)
def test_a_bad_entry_fails_naming_its_field(
    tmp_path: Path, changed: dict[str, Any], field: str
) -> None:
    """The error says which field to fix."""
    with pytest.raises(ValueError, match=field):
        checked_entries(listed(tmp_path, scrapers(**changed)))


def test_a_license_entry_off_surfsense_s_host_fails(tmp_path: Path) -> None:
    """The license key reaches only SurfSense's plugin host, whatever a list says."""
    entry = scrapers(url="https://scrapers.example/mcp", hosts=["scrapers.example"])

    with pytest.raises(ValueError, match="url"):
        checked_entries(listed(tmp_path, entry))


def test_two_entries_with_one_id_fail(tmp_path: Path) -> None:
    """An id names one plugin across the app."""
    with pytest.raises(ValueError, match="scrapers"):
        checked_entries(listed(tmp_path, scrapers(), scrapers()))
