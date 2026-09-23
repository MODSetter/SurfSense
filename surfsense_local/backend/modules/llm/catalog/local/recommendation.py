"""The model to star on this machine: the first in the manifest's order with a
build that runs well here.

The manifest is most preferred first, so walking it and taking the first model
whose own recommended build exists gives a smaller build of the preferred model
before a smaller model. Only curated models are ever starred: a searched or
downloaded model has no reviewed place in any order.
"""

from collections.abc import Sequence

from modules.llm.catalog.local.rows import LocalRow, Origin


def recommended_model(rows_in_manifest_order: Sequence[LocalRow]) -> str | None:
    return next(
        (
            row.id
            for row in rows_in_manifest_order
            if row.origin is Origin.CURATED
            and row.runnable
            and any(build.recommended for build in row.builds)
        ),
        None,
    )
