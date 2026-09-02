"""A sanitized segment must never be a name the store's namespace rejects.

A folder literally named ``.`` (or ``..``) reached ``allocate_path`` during the
fleet seed (ws 38003) and raised ``StorePathError: Illegal path segment: '.'``,
which aborts the *whole* workspace. ``validate_segments`` is the assertion; the
sanitizer is what must guarantee a legal segment, so the guard lives there once
instead of at every caller.
"""

import pytest

from app.knowledge_store.paths import (
    allocate_path,
    normalize_filename,
    safe_folder_segment,
)
from app.knowledge_store.paths.store_path import validate_segments

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("raw", [".", "..", " . ", "  ..  ", "\t.."])
def test_safe_folder_segment_never_yields_a_traversal_segment(raw):
    seg = safe_folder_segment(raw)
    assert seg not in (".", "..")
    validate_segments((seg,))  # the choke point must accept it


@pytest.mark.parametrize("raw", [".", ".."])
def test_normalize_filename_never_yields_a_traversal_segment(raw):
    name = normalize_filename(raw)
    assert name not in (".", "..")
    validate_segments((name,))


def test_allocate_path_survives_a_dot_folder():
    # The exact ws 38003 shape: a body-bearing doc under a folder named ".".
    path = allocate_path(name="Weekly notes", folder_parts=(".",), taken=set())
    assert path.folder_parts[0] not in (".", "..")
    assert path.name  # the filename is still there
