"""Build a short, honest source label for a retrieved document.

A label orients the model about where a passage came from — e.g. ``Slack`` or
``Web · docs.python.org``. It is derived only from the document's type and any
URL in its metadata, so it never asserts detail we don't actually have.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_FRIENDLY_NAMES = {
    "FILE": "File",
    "NOTE": "Note",
    "EXTENSION": "Saved page",
    "CRAWLED_URL": "Web",
    "YOUTUBE_VIDEO": "YouTube",
    "SLACK_CONNECTOR": "Slack",
    "TEAMS_CONNECTOR": "Teams",
    "DISCORD_CONNECTOR": "Discord",
    "NOTION_CONNECTOR": "Notion",
    "GITHUB_CONNECTOR": "GitHub",
    "LINEAR_CONNECTOR": "Linear",
    "JIRA_CONNECTOR": "Jira",
    "CONFLUENCE_CONNECTOR": "Confluence",
    "CLICKUP_CONNECTOR": "ClickUp",
    "AIRTABLE_CONNECTOR": "Airtable",
    "OBSIDIAN_CONNECTOR": "Obsidian",
    "BOOKSTACK_CONNECTOR": "BookStack",
}

_URL_KEYS = ("url", "source_url", "link", "source")


def source_label(document_type: str | None, metadata: dict[str, Any]) -> str | None:
    """``Source`` or ``Source · host``; ``None`` when nothing is known."""
    name = _friendly_name(document_type)
    host = _url_host(metadata)
    if name and host:
        return f"{name} · {host}"
    return name or host


def _friendly_name(document_type: str | None) -> str | None:
    if not document_type:
        return None
    return _FRIENDLY_NAMES.get(document_type, _prettify(document_type))


def _prettify(document_type: str) -> str:
    """Fallback name for unmapped types: ``GOOGLE_DRIVE_FILE`` → ``Google Drive``."""
    words = document_type.replace("_CONNECTOR", "").replace("_FILE", "").split("_")
    return " ".join(word.capitalize() for word in words if word)


def _url_host(metadata: dict[str, Any]) -> str | None:
    for key in _URL_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            host = urlparse(value).netloc
            if host:
                return host.removeprefix("www.")
    return None


__all__ = ["source_label"]
