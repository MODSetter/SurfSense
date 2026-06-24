"""Unit tests for the citation registry spine (ADR 0001 §3)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
    make_key,
)


def test_register_assigns_monotonic_labels() -> None:
    registry = CitationRegistry()

    first = registry.register(
        CitationSourceType.KB_CHUNK, {"document_id": 42, "chunk_id": 880}
    )
    second = registry.register(
        CitationSourceType.KB_CHUNK, {"document_id": 42, "chunk_id": 881}
    )

    assert (first, second) == (1, 2)
    assert registry.next_n == 3


def test_register_is_find_or_create_for_same_unit() -> None:
    registry = CitationRegistry()
    locator = {"document_id": 42, "chunk_id": 880}

    first = registry.register(CitationSourceType.KB_CHUNK, locator)
    again = registry.register(CitationSourceType.KB_CHUNK, locator)

    assert first == again == 1
    assert len(registry.by_n) == 1
    assert registry.next_n == 2


def test_dedup_is_insensitive_to_locator_key_order() -> None:
    registry = CitationRegistry()

    first = registry.register(
        CitationSourceType.KB_CHUNK, {"document_id": 42, "chunk_id": 880}
    )
    reordered = registry.register(
        CitationSourceType.KB_CHUNK, {"chunk_id": 880, "document_id": 42}
    )

    assert first == reordered


def test_same_locator_values_across_types_do_not_collide() -> None:
    registry = CitationRegistry()

    chunk = registry.register(CitationSourceType.KB_CHUNK, {"id": 7})
    chat = registry.register(CitationSourceType.CHAT_TURN, {"id": 7})

    assert chunk != chat


def test_resolve_returns_entry_with_locator_and_display() -> None:
    registry = CitationRegistry()
    n = registry.register(
        CitationSourceType.WEB_RESULT,
        {"url": "https://example.com"},
        {"title": "Example"},
    )

    entry = registry.resolve(n)

    assert entry is not None
    assert entry.n == n
    assert entry.source_type is CitationSourceType.WEB_RESULT
    assert entry.locator == {"url": "https://example.com"}
    assert entry.display == {"title": "Example"}


def test_resolve_unknown_label_returns_none() -> None:
    registry = CitationRegistry()

    assert registry.resolve(999) is None


def test_registry_round_trips_through_serialization() -> None:
    registry = CitationRegistry()
    registry.register(
        CitationSourceType.KB_CHUNK,
        {"document_id": 42, "chunk_id": 880},
        {"title": "Q3 Launch Notes"},
    )

    restored = CitationRegistry.model_validate(registry.model_dump())

    entry = restored.resolve(1)
    assert entry is not None
    assert entry.source_type is CitationSourceType.KB_CHUNK
    assert restored.next_n == registry.next_n


def test_make_key_is_stable_and_type_prefixed() -> None:
    key_a = make_key(CitationSourceType.KB_CHUNK, {"document_id": 42, "chunk_id": 880})
    key_b = make_key(CitationSourceType.KB_CHUNK, {"chunk_id": 880, "document_id": 42})

    assert key_a == key_b
    assert key_a.startswith("kb_chunk|")
