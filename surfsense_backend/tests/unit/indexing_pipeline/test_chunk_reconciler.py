"""reconcile(): diff existing chunk rows against new chunk texts.

The reconciler decides which rows (and embeddings) survive an edit, which texts
must be embedded, and which rows go away -- purely from content, no DB.
"""

from __future__ import annotations

from app.indexing_pipeline.chunk_reconciler import ExistingChunk, reconcile


def _existing(*contents: str) -> list[ExistingChunk]:
    return [
        ExistingChunk(id=i + 1, content=text, position=i)
        for i, text in enumerate(contents)
    ]


def test_identical_content_keeps_every_row_untouched():
    plan = reconcile(_existing("alpha", "beta", "gamma"), ["alpha", "beta", "gamma"])

    assert plan.to_embed == []
    assert plan.to_delete == []
    assert plan.reused == []


def test_head_insert_embeds_only_the_new_chunk_and_shifts_the_rest():
    plan = reconcile(_existing("alpha", "beta"), ["intro", "alpha", "beta"])

    assert plan.to_embed == [(0, "intro")]
    assert plan.to_delete == []
    # alpha: position 0 -> 1, beta: 1 -> 2; embeddings untouched.
    assert plan.reused == [(1, 1), (2, 2)]


def test_middle_edit_swaps_exactly_one_chunk():
    plan = reconcile(
        _existing("alpha", "beta", "gamma"), ["alpha", "beta EDITED", "gamma"]
    )

    assert plan.to_embed == [(1, "beta EDITED")]
    assert plan.to_delete == [2]
    # Neighbours did not move, so no position writes at all.
    assert plan.reused == []


def test_removed_chunk_is_deleted_and_followers_shift_up():
    plan = reconcile(_existing("alpha", "beta", "gamma"), ["alpha", "gamma"])

    assert plan.to_embed == []
    assert plan.to_delete == [2]
    assert plan.reused == [(3, 1)]


def test_duplicate_texts_pair_up_one_to_one():
    # Two identical boilerplate chunks, only one survives the edit: exactly one
    # row is kept and exactly one is deleted -- never both kept or both dropped.
    plan = reconcile(_existing("boiler", "boiler", "body"), ["boiler", "body"])

    assert plan.to_embed == []
    assert plan.to_delete == [2]
    assert plan.reused == [(3, 1)]


def test_duplicate_growth_embeds_only_the_extra_copy():
    plan = reconcile(_existing("boiler", "body"), ["boiler", "boiler", "body"])

    assert plan.to_embed == [(1, "boiler")]
    assert plan.to_delete == []
    assert plan.reused == [(2, 2)]


def test_reorder_becomes_position_updates_with_no_embedding():
    plan = reconcile(_existing("alpha", "beta"), ["beta", "alpha"])

    assert plan.to_embed == []
    assert plan.to_delete == []
    assert sorted(plan.reused) == [(1, 1), (2, 0)]


def test_full_rewrite_replaces_everything():
    plan = reconcile(_existing("alpha", "beta"), ["new one", "new two"])

    assert plan.to_embed == [(0, "new one"), (1, "new two")]
    assert sorted(plan.to_delete) == [1, 2]
    assert plan.reused == []


def test_no_existing_chunks_embeds_all():
    plan = reconcile([], ["alpha", "beta"])

    assert plan.to_embed == [(0, "alpha"), (1, "beta")]
    assert plan.to_delete == []
    assert plan.reused == []
