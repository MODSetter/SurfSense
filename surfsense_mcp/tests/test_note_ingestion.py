"""The note-to-document envelope mapping."""

from __future__ import annotations

from surfsense_mcp.features.knowledge_base.note_ingestion import build_note_document


def test_builds_extension_document_with_content():
    doc = build_note_document(
        workspace_id=3, title="Meeting notes", content="body", source_url=None
    )
    assert doc["document_type"] == "EXTENSION"
    assert doc["workspace_id"] == 3
    entry = doc["content"][0]
    assert entry["pageContent"] == "body"
    assert entry["metadata"]["VisitedWebPageTitle"] == "Meeting notes"


def test_synthesizes_url_when_none_given():
    doc = build_note_document(
        workspace_id=1, title="Q3 Plan!", content="x", source_url=None
    )
    url = doc["content"][0]["metadata"]["VisitedWebPageURL"]
    assert url.startswith("https://surfsense.local/mcp-note/q3-plan-")


def test_keeps_provided_source_url():
    doc = build_note_document(
        workspace_id=1, title="t", content="x", source_url="https://example.com/a"
    )
    assert doc["content"][0]["metadata"]["VisitedWebPageURL"] == "https://example.com/a"
