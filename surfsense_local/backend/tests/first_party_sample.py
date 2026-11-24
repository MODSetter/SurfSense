"""A first-party plugin list holding one sample plugin, for the tests of how SurfSense's own plugins connect.

The packaged list is empty since SurfSense's scrapers left the app; the machinery
that lists, connects and checks a first-party plugin stays.
"""

import json
from pathlib import Path

import pytest

from modules.plugins.lists.first_party import first_party_icon, first_party_list
from modules.plugins.lists.registry import offered_entry

SAMPLE_ID = "news"
SAMPLE_TOOL = "search_articles"
_ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7"/></svg>'


def use_sample_first_party_list(monkeypatch: pytest.MonkeyPatch, folder: Path) -> Path:
    """Write the sample list and its icon under `folder`, and point the app at it."""
    path = folder / "plugins.json"
    (folder / "icons").mkdir(parents=True, exist_ok=True)
    (folder / "icons" / f"{SAMPLE_ID}.svg").write_text(_ICON, encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "plugins": [
                    {
                        "id": SAMPLE_ID,
                        "kind": "remote",
                        "name": "News",
                        "description": "Search the news.",
                        "author": "SurfSense",
                        "url": f"https://plugins.surfsense.com/{SAMPLE_ID}/mcp",
                        "auth": {"type": "license"},
                        "hosts": ["plugins.surfsense.com"],
                        "access": "license",
                        "icon": f"{SAMPLE_ID}.svg",
                        "tools": [SAMPLE_TOOL],
                        "added": "2026-10",
                        "about": "A sample of SurfSense's own plugins, for tests.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # Each module that reads the list took its path by name.
    for module in (first_party_list, first_party_icon, offered_entry):
        monkeypatch.setattr(module, "FIRST_PARTY_LIST", path)
    return path
