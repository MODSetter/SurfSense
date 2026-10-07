"""A workbook the agent's script wrote, its formulas recalculated by LibreOffice when Office support is on.

Previews and Studio's viewer show cached values, and a script's library caches
none or 0 (04, decision 17). The version records what happened so the render
result can say whether the values shown are real.
"""

import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.office_support import OfficeRunError, engine
from worker.studio.script_document.cached_values import (
    count_formulas,
    with_cached_values,
)

logger = logging.getLogger(__name__)

# Measured at 1 to 5 s; the render tool waits 150 s for the job, the script up to 120 s of it.
RECALC_SECONDS = 45
OFFICE_OFF = "Office support is off."


@dataclass(frozen=True)
class Recalculation:
    """The workbook to deliver, and the record the version keeps; None without formulas."""

    data: bytes
    record: dict[str, Any] | None

    @property
    def recalculated(self) -> bool:
        return self.record is not None and self.record["by"] is not None


def recalculate(data: bytes) -> Recalculation:
    """Cache LibreOffice's value for every formula, keeping the formulas and fullCalcOnLoad."""
    formulas = count_formulas(data)
    if formulas == 0:
        return Recalculation(data, None)
    office = engine.office_engine()
    if office is None:
        return Recalculation(data, _not_recalculated(formulas, OFFICE_OFF))
    try:
        with tempfile.TemporaryDirectory(prefix="surfsense-recalc-") as scratch:
            workbook = Path(scratch) / "workbook.xlsx"
            workbook.write_bytes(data)
            values = office.values_of(
                workbook, deadline=time.monotonic() + RECALC_SECONDS
            )
    except OfficeRunError as error:
        return Recalculation(data, _not_recalculated(formulas, str(error)))
    # The workbook is made; a recalculation that breaks must not fail it.
    except Exception:
        logger.exception("recalculating a workbook failed")
        return Recalculation(data, _not_recalculated(formulas, "Recalculating failed."))
    cached = with_cached_values(data, values)
    return Recalculation(
        cached.data,
        {
            "by": office.name,
            "formulas": cached.written,
            "left_blank": cached.left_blank,
            "reason": None,
        },
    )


def _not_recalculated(formulas: int, reason: str) -> dict[str, Any]:
    return {"by": None, "formulas": formulas, "left_blank": 0, "reason": reason}
