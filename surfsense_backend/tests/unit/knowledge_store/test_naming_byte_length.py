"""Derived path components must fit the filesystem's 255-byte per-component limit."""

import pytest

from app.knowledge_store.paths import (
    allocate_path,
    normalize_filename,
    safe_folder_segment,
)

pytestmark = pytest.mark.unit

_MAX_COMPONENT_BYTES = 255


def test_normalize_filename_fits_byte_limit_for_multibyte_title():
    title = "低空经济政策对比" * 25  # 200 chars, 600 UTF-8 bytes
    name = normalize_filename(title)
    assert len(name.encode("utf-8")) <= _MAX_COMPONENT_BYTES


def test_safe_folder_segment_fits_byte_limit_for_multibyte_name():
    name = "低空经济政策对比" * 25
    seg = safe_folder_segment(name)
    assert len(seg.encode("utf-8")) <= _MAX_COMPONENT_BYTES


def test_allocate_path_disambiguation_stays_within_byte_limit():
    name = "低空经济政策对比" * 25
    taken: set[str] = set()
    first = allocate_path(name=name, folder_parts=(), taken=taken)
    second = allocate_path(name=name, folder_parts=(), taken=taken)
    assert first.virtual_path != second.virtual_path
    assert len(second.name.encode("utf-8")) <= _MAX_COMPONENT_BYTES


def test_derived_name_is_writable_where_raw_title_is_not(tmp_path):
    raw = "低空经济政策对比" * 25 + ".xlsx"
    with pytest.raises(OSError):
        (tmp_path / raw).write_bytes(b"x")
    safe = normalize_filename(raw)
    (tmp_path / safe).write_bytes(b"x")
    assert (tmp_path / safe).read_bytes() == b"x"
