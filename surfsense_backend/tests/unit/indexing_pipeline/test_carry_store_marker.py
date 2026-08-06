import pytest

from app.indexing_pipeline.indexing_pipeline_service import _carry_store_marker
from app.knowledge_store.paths import PATH_MARKER

pytestmark = pytest.mark.unit


def test_marker_survives_a_connector_resync_that_omits_it():
    """A re-sync's fresh metadata has no path marker; the store's must be kept,
    or ingest re-authors a new path and forks the document into a duplicate."""
    existing = {PATH_MARKER: "documents/Untitled document.md", "md5_checksum": "old"}
    incoming = {"md5_checksum": "new", "FILE_NAME": "Untitled document"}

    merged = _carry_store_marker(existing, incoming)

    assert merged[PATH_MARKER] == "documents/Untitled document.md"
    assert merged["md5_checksum"] == "new"
    assert merged["FILE_NAME"] == "Untitled document"


def test_incoming_marker_wins_when_present():
    existing = {PATH_MARKER: "documents/old.md"}
    incoming = {PATH_MARKER: "documents/new.md"}

    assert _carry_store_marker(existing, incoming)[PATH_MARKER] == "documents/new.md"


def test_no_marker_anywhere_is_a_plain_copy():
    assert _carry_store_marker(None, {"a": 1}) == {"a": 1}
    assert _carry_store_marker({"a": 1}, None) == {}
