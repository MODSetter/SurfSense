"""Lock the ``Metadata`` ``extra='allow'`` contract — the only schema
that does. Free-form annotations on definitions (e.g. ``owner``,
``project``, ``created_by_ai``) need to round-trip through the envelope
without being rejected.
"""

from __future__ import annotations

import pytest

from app.automations.schemas.definition.metadata import Metadata

pytestmark = pytest.mark.unit


def test_metadata_preserves_unknown_keys() -> None:
    """Unlike every other definition sub-schema, ``Metadata`` allows
    extra keys and round-trips them — that's its purpose."""
    metadata = Metadata.model_validate(
        {
            "tags": ["weekly", "report"],
            "owner": "tg",
            "created_by_ai": True,
        }
    )

    dumped = metadata.model_dump()

    assert dumped["tags"] == ["weekly", "report"]
    assert dumped["owner"] == "tg"
    assert dumped["created_by_ai"] is True


def test_metadata_defaults_tags_to_empty_list() -> None:
    """No tags is the common case; the default is the empty list so
    callers can append without a None check."""
    assert Metadata().tags == []
