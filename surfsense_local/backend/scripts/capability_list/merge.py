"""Rows added to a capability list without displacing the ones it has."""

from modules.llm.capability.match_key import match_key
from modules.llm.capability.measured.schema import CapabilityList, MeasuredModel


def merged(
    existing: CapabilityList, added: list[MeasuredModel]
) -> tuple[CapabilityList, list[MeasuredModel]]:
    """The list with every added row no kept row already names, and the rows left out.

    Existing keys win, by the looser key too, so the ladder's 8-case rows stand
    over a screening and a screening over an assumption.
    """
    taken = {name for row in existing.models for name in _names(row)}
    kept: list[MeasuredModel] = []
    left_out: list[MeasuredModel] = []
    for row in added:
        names = _names(row)
        if names & taken:
            left_out.append(row)
            continue
        kept.append(row)
        taken |= names
    rows = existing.model_copy(update={"models": [*existing.models, *kept]})
    # Validated again: the result is what the app will load.
    return CapabilityList.model_validate(rows.model_dump()), left_out


def _names(row: MeasuredModel) -> set[str]:
    """Every key a row is found by, exact and loose."""
    return {name for key in row.match.keys for name in (key, match_key(key)) if name}
