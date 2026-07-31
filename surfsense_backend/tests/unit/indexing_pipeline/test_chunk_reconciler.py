"""reconcile(): diff existing chunk rows against new chunk texts.

The reconciler decides which rows (and embeddings) survive an edit, which texts
must be embedded, and which rows go away -- purely from content, no DB.

Fixtures lay one chunk out per line, so chunk ``i`` sits on line ``i + 1``. That
keeps line ranges in step with positions unless a test deliberately moves them.
"""

from __future__ import annotations

from app.indexing_pipeline.chunk_reconciler import (
    ExistingChunk,
    PendingChunk,
    ReusedChunk,
    reconcile,
)
from app.indexing_pipeline.document_chunker import LineChunk


def _existing(*contents: str) -> list[ExistingChunk]:
    return [
        ExistingChunk(
            id=i + 1, content=text, position=i, start_line=i + 1, end_line=i + 1
        )
        for i, text in enumerate(contents)
    ]


def _new(*contents: str) -> list[LineChunk]:
    return [
        LineChunk(text=text, start_line=i + 1, end_line=i + 1)
        for i, text in enumerate(contents)
    ]


def test_identical_content_keeps_every_row_untouched():
    plan = reconcile(
        _existing("alpha", "beta", "gamma"), _new("alpha", "beta", "gamma")
    )

    assert plan.to_embed == []
    assert plan.to_delete == []
    assert plan.reused == []


def test_head_insert_embeds_only_the_new_chunk_and_shifts_the_rest():
    plan = reconcile(_existing("alpha", "beta"), _new("intro", "alpha", "beta"))

    assert plan.to_embed == [PendingChunk(0, "intro", 1, 1)]
    assert plan.to_delete == []
    # alpha: position 0 -> 1, beta: 1 -> 2; embeddings untouched.
    assert plan.reused == [ReusedChunk(1, 1, 2, 2), ReusedChunk(2, 2, 3, 3)]


def test_middle_edit_swaps_exactly_one_chunk():
    plan = reconcile(
        _existing("alpha", "beta", "gamma"), _new("alpha", "beta EDITED", "gamma")
    )

    assert plan.to_embed == [PendingChunk(1, "beta EDITED", 2, 2)]
    assert plan.to_delete == [2]
    # Neighbours did not move, so no writes at all.
    assert plan.reused == []


def test_unchanged_text_that_moved_lines_is_still_written_back():
    """An edit above a chunk shifts its lines without moving its position.

    The embedding survives, but the stored line range is now wrong -- so the row
    has to be updated even though nothing about it looks like it moved.
    """
    existing = _existing("alpha", "beta")
    new_chunks = [
        LineChunk(text="alpha GREW", start_line=1, end_line=2),
        LineChunk(text="beta", start_line=3, end_line=3),
    ]

    plan = reconcile(existing, new_chunks)

    assert plan.to_embed == [PendingChunk(0, "alpha GREW", 1, 2)]
    assert plan.to_delete == [1]
    assert plan.reused == [ReusedChunk(2, 1, 3, 3)]


def test_removed_chunk_is_deleted_and_followers_shift_up():
    plan = reconcile(_existing("alpha", "beta", "gamma"), _new("alpha", "gamma"))

    assert plan.to_embed == []
    assert plan.to_delete == [2]
    assert plan.reused == [ReusedChunk(3, 1, 2, 2)]


def test_duplicate_texts_pair_up_one_to_one():
    # Two identical boilerplate chunks, only one survives the edit: exactly one
    # row is kept and exactly one is deleted -- never both kept or both dropped.
    plan = reconcile(_existing("boiler", "boiler", "body"), _new("boiler", "body"))

    assert plan.to_embed == []
    assert plan.to_delete == [2]
    assert plan.reused == [ReusedChunk(3, 1, 2, 2)]


def test_duplicate_growth_embeds_only_the_extra_copy():
    plan = reconcile(_existing("boiler", "body"), _new("boiler", "boiler", "body"))

    assert plan.to_embed == [PendingChunk(1, "boiler", 2, 2)]
    assert plan.to_delete == []
    assert plan.reused == [ReusedChunk(2, 2, 3, 3)]


def test_reorder_becomes_position_updates_with_no_embedding():
    plan = reconcile(_existing("alpha", "beta"), _new("beta", "alpha"))

    assert plan.to_embed == []
    assert plan.to_delete == []
    assert sorted(plan.reused, key=lambda r: r.id) == [
        ReusedChunk(1, 1, 2, 2),
        ReusedChunk(2, 0, 1, 1),
    ]


def test_full_rewrite_replaces_everything():
    plan = reconcile(_existing("alpha", "beta"), _new("new one", "new two"))

    assert plan.to_embed == [
        PendingChunk(0, "new one", 1, 1),
        PendingChunk(1, "new two", 2, 2),
    ]
    assert sorted(plan.to_delete) == [1, 2]
    assert plan.reused == []


def test_no_existing_chunks_embeds_all():
    plan = reconcile([], _new("alpha", "beta"))

    assert plan.to_embed == [
        PendingChunk(0, "alpha", 1, 1),
        PendingChunk(1, "beta", 2, 2),
    ]
    assert plan.to_delete == []
    assert plan.reused == []


def test_spanless_legacy_row_is_backfilled():
    """Rows written before spans existed carry NULL; matching them rewrites them."""
    existing = [ExistingChunk(id=7, content="alpha", position=0)]

    plan = reconcile(existing, _new("alpha"))

    assert plan.to_embed == []
    assert plan.to_delete == []
    assert plan.reused == [ReusedChunk(7, 0, 1, 1)]
