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
        "name": "SurfSense Scrapers",
        "description": "Search the web and scrape sites.",
        "author": "SurfSense",
        "url": "https://plugins.surfsense.com/scrapers/mcp",
        "auth": {"type": "license"},
        "hosts": ["plugins.surfsense.com"],
        "access": "license",
        "tools": ["scrape"],
        "added": "2026-10",
        "about": "Scrape sites and search the web, read as clean text.",
    }
    return {**entry, **changed}


def listed(tmp_path: Path, *entries: dict[str, Any]) -> Path:
    """A first-party list file holding `entries`."""
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"schema_version": 1, "plugins": list(entries)}))
    return path


def test_the_list_is_read_as_utf_8_whatever_the_system_code_page(
    tmp_path: Path,
) -> None:
    """The shipped list holds curly apostrophes, and Windows reads in its code page unless told."""
    about = "Read a site\u2019s pages as clean text."
    path = tmp_path / "plugins.json"
    path.write_bytes(
        json.dumps(
            {"schema_version": 1, "plugins": [scrapers(about=about)]},
            ensure_ascii=False,
        ).encode("utf-8")
    )

    assert checked_entries(path)[0].about == about


def test_the_packaged_list_passes_its_check() -> None:
    """A bad entry fails CI here, not on a user's machine."""
    assert [entry.id for entry in checked_entries(FIRST_PARTY_LIST)] == [
        "google-search",
        "web-crawl",
        "reddit",
        "youtube",
        "instagram",
        "tiktok",
        "google-maps",
        "amazon",
        "walmart",
        "indeed",
    ]


def test_each_scraper_plugin_is_its_own_server_on_the_plugin_host() -> None:
    """One host, so one consent; a path each, so a server each."""
    entries = checked_entries(FIRST_PARTY_LIST)

    assert {entry.url for entry in entries} == {
        f"https://plugins.surfsense.com/{entry.id}/mcp" for entry in entries
    }
    assert {tuple(entry.hosts) for entry in entries} == {("plugins.surfsense.com",)}
    assert {entry.access for entry in entries} == {"license"}


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
        ({"verification": "verified"}, "verification"),
        ({"access": "external"}, "access_note"),
        ({"name": ""}, "name"),
        ({"about": "a" * 601}, "about"),
        ({"tools": ["has space"]}, "tools"),
        ({"tools": ["scrape", "scrape"]}, "tools"),
        ({"added": "2026-13"}, "added"),
        ({"added": "October 2026"}, "added"),
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


def test_every_packaged_entry_has_its_icon_beside_the_list() -> None:
    """The screen shows each of SurfSense's plugins with its logo, from the app."""
    entries = checked_entries(FIRST_PARTY_LIST)

    assert all(entry.icon for entry in entries)
    assert all(
        (FIRST_PARTY_LIST.with_name("icons") / entry.icon).is_file()
        for entry in entries
        if entry.icon
    )


def test_an_icon_missing_beside_the_list_fails(tmp_path: Path) -> None:
    """A typo in the file name fails CI rather than showing a letter."""
    with pytest.raises(ValueError, match="scrapers: icon"):
        checked_entries(listed(tmp_path, scrapers(icon="scrapers.svg")))


def test_an_icon_name_reaching_outside_its_folder_fails(tmp_path: Path) -> None:
    """Only a plain file name in icons/ is served."""
    (tmp_path / "secret.svg").write_text("<svg/>")

    with pytest.raises(ValueError, match="scrapers: icon"):
        checked_entries(listed(tmp_path, scrapers(icon="../secret.svg")))


def test_a_first_party_entry_must_list_its_tools(tmp_path: Path) -> None:
    """Its page shows them before it is connected; the plugin host checks them."""
    with pytest.raises(ValueError, match="scrapers: tools"):
        checked_entries(listed(tmp_path, scrapers(tools=None)))


def test_every_packaged_entry_lists_its_tools() -> None:
    """The real list passes the rule above."""
    assert all(entry.tools for entry in checked_entries(FIRST_PARTY_LIST))


def test_a_first_party_entry_must_say_when_it_was_added(tmp_path: Path) -> None:
    """Its public page says which month it joined the list."""
    with pytest.raises(ValueError, match="scrapers: added"):
        checked_entries(listed(tmp_path, scrapers(added=None)))


def test_a_first_party_entry_must_say_more_about_itself(tmp_path: Path) -> None:
    """Its public page shows `about`, never its card's description in its place."""
    with pytest.raises(ValueError, match="scrapers: about"):
        checked_entries(listed(tmp_path, scrapers(about=None)))
