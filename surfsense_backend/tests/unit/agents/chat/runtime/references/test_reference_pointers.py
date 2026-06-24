"""Tests for reference pointer rendering."""

from __future__ import annotations

import pytest

from app.agents.chat.runtime.references import (
    ReferenceKind,
    ResolvedReference,
    render_reference_pointers,
)

pytestmark = pytest.mark.unit


def test_returns_none_when_no_references() -> None:
    assert render_reference_pointers([]) is None


def test_wraps_block_and_keeps_reference_order() -> None:
    block = render_reference_pointers(
        [
            ResolvedReference(
                kind=ReferenceKind.DOCUMENT, entity_id=42, label="Q3 Notes"
            ),
            ResolvedReference(kind=ReferenceKind.CHAT, entity_id=5, label="Pricing"),
        ]
    )

    assert block is not None
    assert block.startswith("<referenced_this_turn>")
    assert block.endswith("</referenced_this_turn>")
    assert block.index("document 42") < block.index("chat 5")


def test_document_with_path_shows_title_and_path() -> None:
    block = render_reference_pointers(
        [
            ResolvedReference(
                kind=ReferenceKind.DOCUMENT,
                entity_id=42,
                label="Q3 Launch Notes",
                path="/documents/Launch/Q3.xml",
            )
        ]
    )

    assert block is not None
    assert '- document 42 — "Q3 Launch Notes" (/documents/Launch/Q3.xml)' in block


def test_folder_with_path_renders_with_folder_kind() -> None:
    block = render_reference_pointers(
        [
            ResolvedReference(
                kind=ReferenceKind.FOLDER,
                entity_id=7,
                label="Specs",
                path="/documents/Specs/",
            )
        ]
    )

    assert block is not None
    assert '- folder 7 — "Specs" (/documents/Specs/)' in block


def test_connector_shows_provider_and_account() -> None:
    block = render_reference_pointers(
        [
            ResolvedReference(
                kind=ReferenceKind.CONNECTOR,
                entity_id=12,
                label="work@acme.com",
                provider="Gmail",
            )
        ]
    )

    assert block is not None
    assert "- connector 12 — Gmail (work@acme.com)" in block


def test_connector_without_provider_falls_back_to_label() -> None:
    block = render_reference_pointers(
        [
            ResolvedReference(
                kind=ReferenceKind.CONNECTOR, entity_id=12, label="work@acme.com"
            )
        ]
    )

    assert block is not None
    assert "- connector 12 — work@acme.com" in block


def test_chat_shows_quoted_title() -> None:
    block = render_reference_pointers(
        [ResolvedReference(kind=ReferenceKind.CHAT, entity_id=5, label="Pricing debate")]
    )

    assert block is not None
    assert '- chat 5 — "Pricing debate"' in block


def test_label_whitespace_is_collapsed_to_one_line() -> None:
    block = render_reference_pointers(
        [
            ResolvedReference(
                kind=ReferenceKind.DOCUMENT,
                entity_id=1,
                label="line one\nline two",
            )
        ]
    )

    assert block is not None
    assert '- document 1 — "line one line two"' in block
