"""Translate a plain note into SurfSense's document-ingestion envelope.

The REST API ingests free text through the browser-extension document shape
(title + page content + visit metadata); the backend then chunks and embeds it
like any saved page. Isolating that mapping lets the KB tool offer a simple
title+content surface without leaking the envelope's shape.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone


def build_note_document(
    *, workspace_id: int, title: str, content: str, source_url: str | None
) -> dict:
    """Wrap a note in the EXTENSION document payload the create endpoint expects."""
    # ponytail: reuses the extension-ingestion path to add free text. Ceiling —
    # visit metadata is synthesized; the "real page URL" is a stable synthetic
    # link derived from the title. Upgrade path: a first-class note endpoint.
    captured_at = datetime.now(timezone.utc).isoformat()
    return {
        "document_type": "EXTENSION",
        "workspace_id": workspace_id,
        "content": [
            {
                "metadata": {
                    "BrowsingSessionId": "surfsense-mcp",
                    "VisitedWebPageURL": source_url or _synthetic_url(title),
                    "VisitedWebPageTitle": title,
                    "VisitedWebPageDateWithTimeInISOString": captured_at,
                    "VisitedWebPageReffererURL": "",
                    "VisitedWebPageVisitDurationInMilliseconds": "0",
                },
                "pageContent": content,
            }
        ],
    }


def _synthetic_url(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-") or "note"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"https://surfsense.local/mcp-note/{slug}-{stamp}"
