"""Content-addressing: equal (bytes + recipe) must map to one storage location.

This is the dedup guarantee the whole cache rests on -- two users uploading the
same file under the same parser settings have to land on the same object key, and
any change to bytes or recipe has to land somewhere else.
"""

from __future__ import annotations

import pytest

from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.storage.object_keys import (
    CACHE_PREFIX,
    build_parse_object_key,
)

pytestmark = pytest.mark.unit


def _key(**overrides) -> ParseKey:
    base = {
        "source_sha256": "a" * 64,
        "etl_service": "LLAMACLOUD",
        "mode": "basic",
        "version": 1,
    }
    base.update(overrides)
    return ParseKey.for_document(
        base["source_sha256"],
        etl_service=base["etl_service"],
        mode=base["mode"],
        version=base["version"],
    )


def test_same_bytes_and_recipe_produce_the_same_object_key():
    assert build_parse_object_key(_key()) == build_parse_object_key(_key())


def test_different_bytes_produce_different_object_keys():
    assert build_parse_object_key(
        _key(source_sha256="a" * 64)
    ) != build_parse_object_key(_key(source_sha256="b" * 64))


@pytest.mark.parametrize(
    "field, value",
    [
        ("etl_service", "DOCLING"),
        ("mode", "premium"),
        ("version", 2),
    ],
)
def test_any_recipe_change_produces_a_different_object_key(field, value):
    # Same bytes but a different parser/mode/version must not collide: the recipe
    # is part of the identity, so changing it has to re-parse, not reuse.
    assert build_parse_object_key(_key()) != build_parse_object_key(
        _key(**{field: value})
    )


def test_object_key_is_prefixed_and_sharded_by_source_hash():
    # Shape matters operationally: a dedicated top-level prefix keeps cache blobs
    # out of the normal store, and the sha directory groups every recipe variant
    # of one file together.
    key = _key()
    assert build_parse_object_key(key) == (
        f"{CACHE_PREFIX}/{key.source_sha256}/LLAMACLOUD.basic.v1.md"
    )
