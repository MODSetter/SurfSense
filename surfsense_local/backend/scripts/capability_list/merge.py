"""Rows added to a capability list, each model kept once by its strongest row."""

from dataclasses import dataclass

from modules.llm.capability.match_key import match_key
from modules.llm.capability.measured.schema import (
    ASSUMED_SUITE,
    SCREEN_SUITE,
    CapabilityList,
    MeasuredModel,
)

# A suite of its own cases outranks the two-case screening, and that an assumption.
_RANK = {SCREEN_SUITE: 1, ASSUMED_SUITE: 0}
_MEASURED = 2


@dataclass(frozen=True)
class LeftOut:
    row: MeasuredModel
    # The row that names the same model and stays.
    kept: MeasuredModel
    # Whether `kept` was already in the list, rather than added beside `row`.
    listed: bool
    # Whether `row` was in the list, and `kept` took its place.
    replaced: bool = False


def merged(
    existing: CapabilityList, added: list[MeasuredModel]
) -> tuple[CapabilityList, list[LeftOut]]:
    """The list with one row per model, by exact or looser key, and the rows left out.

    The stronger row stays, in the list or added: the ladder's 8-case rows over
    a screening, and a screening over an assumption, so a later sweep can
    measure a flagship it assumed. Between rows of one suite the shorter key
    wins, the model's own name over a variant the looser key folds into it
    (gpt-5-2 over gpt-5-2-chat) whatever order the runs came in; and a row
    already listed over an added one with the same key.
    """
    candidates = [(row, True) for row in existing.models] + [
        (row, False) for row in added
    ]
    holders: dict[str, tuple[MeasuredModel, bool]] = {}
    left_out: list[LeftOut] = []
    dropped: set[int] = set()
    for index in sorted(range(len(candidates)), key=lambda at: _weaker(candidates[at])):
        row, listed = candidates[index]
        names = _names(row)
        holder = next((holders[name] for name in names if name in holders), None)
        if holder is not None:
            left_out.append(LeftOut(row, *holder, replaced=listed))
            dropped.add(index)
            continue
        holders.update(dict.fromkeys(names, (row, listed)))
    kept = [row for index, (row, _) in enumerate(candidates) if index not in dropped]
    rows = existing.model_copy(update={"models": kept})
    # Validated again: the result is what the app will load.
    return CapabilityList.model_validate(rows.model_dump()), left_out


def _weaker(candidate: tuple[MeasuredModel, bool]) -> tuple[int, int, bool]:
    """Sorts the strongest first: by suite, then the shorter key, then a listed row."""
    row, listed = candidate
    return (-_RANK.get(row.suite, _MEASURED), len(row.key), not listed)


def _names(row: MeasuredModel) -> set[str]:
    """Every key a row is found by, exact and loose."""
    return {name for key in row.match.keys for name in (key, match_key(key)) if name}
