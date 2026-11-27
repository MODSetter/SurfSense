"""The model to star on this machine: the first in the manifest's order whose
build carries the agent here, else the first with a build that runs well here.

The manifest is most preferred first, so walking it and taking the first model
whose own recommended build exists gives a smaller build of the preferred model
before a smaller model. A model that carries the agent comes first, so a machine
that can run Agentic chats is never steered to a model that can only answer in
Basic. Only curated models are ever starred: a searched or downloaded model has
no reviewed place in any order.
"""

from collections.abc import Sequence, Set

from modules.llm.catalog.local.rows import LocalRow, Origin


def recommended_model(
    rows_in_manifest_order: Sequence[LocalRow],
    carries_the_agent: Set[str] = frozenset(),
) -> str | None:
    """`carries_the_agent` names the rows whose recommended build the load plan
    keeps resident at the agent's window, on a machine that can run it."""
    eligible = [
        row.id
        for row in rows_in_manifest_order
        if row.origin is Origin.CURATED
        and row.runnable
        and any(build.recommended for build in row.builds)
    ]
    return next(
        (row_id for row_id in eligible if row_id in carries_the_agent),
        next(iter(eligible), None),
    )
