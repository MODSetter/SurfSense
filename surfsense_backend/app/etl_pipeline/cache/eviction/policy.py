"""Pure selection rules for which cached entries to drop."""

from __future__ import annotations

from collections.abc import Iterable

from app.etl_pipeline.cache.schemas import EvictionCandidate


def select_over_budget(
    coldest_first: Iterable[EvictionCandidate],
    *,
    current_total_bytes: int,
    max_total_bytes: int,
) -> list[EvictionCandidate]:
    """Pick coldest entries until the footprint drops under the budget."""
    bytes_to_free = current_total_bytes - max_total_bytes
    if bytes_to_free <= 0:
        return []

    chosen: list[EvictionCandidate] = []
    bytes_freed = 0
    for candidate in coldest_first:
        if bytes_freed >= bytes_to_free:
            break
        chosen.append(candidate)
        bytes_freed += candidate.size_bytes
    return chosen
