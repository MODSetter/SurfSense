"""Rows added to a capability list without displacing the ones it has."""

from dataclasses import dataclass

from modules.llm.capability.match_key import match_key
from modules.llm.capability.measured.schema import CapabilityList, MeasuredModel


@dataclass(frozen=True)
class LeftOut:
    row: MeasuredModel
    # The row that names the same model and stays.
    kept: MeasuredModel
    # Whether `kept` was already in the list, rather than added beside `row`.
    listed: bool


def merged(
    existing: CapabilityList, added: list[MeasuredModel]
) -> tuple[CapabilityList, list[LeftOut]]:
    """The list with every added row no kept row already names, and the rows left out.

    Existing keys win, by the looser key too, so the ladder's 8-case rows stand
    over a screening and a screening over an assumption. Between two added
    rows the shorter key wins, the model's own name over a variant the looser
    key folds into it: gpt-5-2 over gpt-5-2-chat, whatever order they came in.
    """
    holders = {name: (row, True) for row in existing.models for name in _names(row)}
    left_out: list[LeftOut] = []
    dropped: set[int] = set()
    for index in sorted(range(len(added)), key=lambda index: len(added[index].key)):
        row = added[index]
        names = _names(row)
        holder = next((holders[name] for name in names if name in holders), None)
        if holder is not None:
            left_out.append(LeftOut(row, *holder))
            dropped.add(index)
            continue
        holders.update(dict.fromkeys(names, (row, False)))
    kept = [row for index, row in enumerate(added) if index not in dropped]
    rows = existing.model_copy(update={"models": [*existing.models, *kept]})
    # Validated again: the result is what the app will load.
    return CapabilityList.model_validate(rows.model_dump()), left_out


def _names(row: MeasuredModel) -> set[str]:
    """Every key a row is found by, exact and loose."""
    return {name for key in row.match.keys for name in (key, match_key(key)) if name}
