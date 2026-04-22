from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.obsidian_plugin import HeadingRef, NotePayload
from app.services.obsidian_plugin_indexer import _build_metadata


def test_build_metadata_serializes_headings_to_plain_json() -> None:
    now = datetime.now(UTC)
    payload = NotePayload(
        vault_id="vault-1",
        path="notes.md",
        name="notes",
        extension="md",
        content="# Notes",
        headings=[HeadingRef(heading="Notes", level=1)],
        content_hash="abc123",
        mtime=now,
        ctime=now,
    )

    metadata = _build_metadata(payload, vault_name="My Vault", connector_id=42)

    assert metadata["headings"] == [{"heading": "Notes", "level": 1}]
