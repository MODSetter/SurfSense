from types import SimpleNamespace

import pytest

from app.knowledge_store.paths import DOCUMENTS_ROOT, PATH_MARKER
from app.knowledge_store.service import _recorded_virtual_path

pytestmark = pytest.mark.unit


def _doc(metadata=None, path=None):
    return SimpleNamespace(document_metadata=metadata, path=path)


def test_marker_is_preferred():
    doc = _doc(
        metadata={PATH_MARKER: f"{DOCUMENTS_ROOT}/from-marker.md"},
        path=f"{DOCUMENTS_ROOT}/from-column.md",
    )
    assert (
        _recorded_virtual_path(doc, DOCUMENTS_ROOT)
        == f"{DOCUMENTS_ROOT}/from-marker.md"
    )


def test_column_is_the_fallback_when_marker_was_wiped():
    """A connector re-sync can drop the marker; the column must still pin the
    file so ingest overwrites in place instead of forking a duplicate."""
    doc = _doc(metadata={"md5_checksum": "x"}, path=f"{DOCUMENTS_ROOT}/kept.md")
    assert _recorded_virtual_path(doc, DOCUMENTS_ROOT) == f"{DOCUMENTS_ROOT}/kept.md"


def test_none_when_neither_names_a_store_path():
    assert _recorded_virtual_path(_doc(), DOCUMENTS_ROOT) is None
    assert _recorded_virtual_path(_doc(path="/elsewhere/x.md"), DOCUMENTS_ROOT) is None
