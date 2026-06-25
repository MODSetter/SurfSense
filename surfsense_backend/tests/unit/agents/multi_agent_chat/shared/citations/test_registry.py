"""Unit tests for the citation registry spine."""

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


def _kb(registry: CitationRegistry, chunk_id: int) -> int:
    return registry.register(
        CitationSourceType.KB_CHUNK, {"document_id": 1, "chunk_id": chunk_id}
    )


def test_merge_unions_disjoint_registries_preserving_labels() -> None:
    left = CitationRegistry()
    _kb(left, 10)  # [1]
    _kb(left, 11)  # [2]

    # A branch that forked from `left`, then registered its own chunk at [3].
    right = left.model_copy(deep=True)
    third = _kb(right, 12)  # [3]
    assert third == 3

    merged = left.merge(right)

    assert merged.resolve(1).locator["chunk_id"] == 10
    assert merged.resolve(2).locator["chunk_id"] == 11
    assert merged.resolve(3).locator["chunk_id"] == 12
    assert merged.next_n == 4


def test_merge_keeps_one_label_for_a_shared_source() -> None:
    left = CitationRegistry()
    _kb(left, 10)  # [1]
    right = CitationRegistry()
    _kb(right, 10)  # also [1], same source

    merged = left.merge(right)

    assert len(merged.by_n) == 1
    assert merged.resolve(1).locator["chunk_id"] == 10
    assert merged.next_n == 2


def test_merge_remints_on_collision_without_losing_sources() -> None:
    # Two branches forked from the same base [1], each minting a *different*
    # source at [2]. Merge must keep both sources, re-minting one.
    base = CitationRegistry()
    _kb(base, 10)  # [1]

    left = base.model_copy(deep=True)
    _kb(left, 11)  # [2] -> chunk 11

    right = base.model_copy(deep=True)
    _kb(right, 12)  # [2] -> chunk 12 (collision)

    merged = left.merge(right)

    chunk_ids = {entry.locator["chunk_id"] for entry in merged.by_n.values()}
    assert chunk_ids == {10, 11, 12}
    assert merged.resolve(2).locator["chunk_id"] == 11  # left wins the slot
    assert merged.resolve(3).locator["chunk_id"] == 12  # right re-minted
    assert merged.next_n == 4


def test_merge_does_not_mutate_inputs() -> None:
    left = CitationRegistry()
    _kb(left, 10)
    right = CitationRegistry()
    _kb(right, 11)

    left.merge(right)

    assert list(left.by_n) == [1]
    assert list(right.by_n) == [1]
