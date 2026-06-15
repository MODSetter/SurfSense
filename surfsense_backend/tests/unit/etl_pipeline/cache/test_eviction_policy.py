"""Size-based eviction: drop just enough of the coldest entries to fit budget.

The caller supplies candidates already ordered coldest-first; this pure rule only
decides how far down that list to cut. It must never over-evict (stop as soon as
the footprint fits) and never promise more than the candidates can free.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.etl_pipeline.cache.eviction.policy import select_over_budget
from app.etl_pipeline.cache.schemas import EvictionCandidate

pytestmark = pytest.mark.unit


def _candidate(id_: int, size_bytes: int) -> EvictionCandidate:
    return EvictionCandidate(
        id=id_,
        storage_key=f"etl_cache/{id_}.md",
        size_bytes=size_bytes,
        last_used_at=datetime(2026, 1, 1, tzinfo=UTC),
        times_reused=0,
    )


def test_over_budget_drops_coldest_until_it_fits():
    # 300 used, budget 100 -> must free >=200. Coldest-first [120, 90, 70];
    # 120+90=210 >=200, so the third (70) is spared.
    coldest_first = [_candidate(1, 120), _candidate(2, 90), _candidate(3, 70)]

    chosen = select_over_budget(
        coldest_first, current_total_bytes=300, max_total_bytes=100
    )

    assert [c.id for c in chosen] == [1, 2]


@pytest.mark.parametrize("current_total_bytes", [100, 80])
def test_within_budget_evicts_nothing(current_total_bytes):
    # At or under budget there is nothing to free, so no blob is touched.
    coldest_first = [_candidate(1, 50), _candidate(2, 50)]

    chosen = select_over_budget(
        coldest_first,
        current_total_bytes=current_total_bytes,
        max_total_bytes=100,
    )

    assert chosen == []


def test_stops_as_soon_as_one_entry_covers_the_overage():
    # Only 10 over budget; the first (cold) entry already frees enough.
    coldest_first = [_candidate(1, 40), _candidate(2, 40)]

    chosen = select_over_budget(
        coldest_first, current_total_bytes=110, max_total_bytes=100
    )

    assert [c.id for c in chosen] == [1]


def test_returns_all_candidates_when_they_cannot_free_enough():
    # Deficit is 500 but candidates only total 150: return everything available
    # rather than looping forever or raising.
    coldest_first = [_candidate(1, 100), _candidate(2, 50)]

    chosen = select_over_budget(
        coldest_first, current_total_bytes=600, max_total_bytes=100
    )

    assert [c.id for c in chosen] == [1, 2]
