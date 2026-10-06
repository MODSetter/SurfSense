"""The capability list shipped with the app, read once per process."""

import logging
from functools import lru_cache
from pathlib import Path

from modules.llm.capability.measured.schema import (
    SCHEMA_VERSION,
    CapabilityList,
    MeasuredModel,
)

__all__ = ["SHIPPED", "find_row", "measured_list"]

LOGGER = logging.getLogger(__name__)
SHIPPED = Path(__file__).with_name("capabilities.json")


@lru_cache
def measured_list() -> CapabilityList:
    try:
        return CapabilityList.model_validate_json(SHIPPED.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        # Losing the list takes nothing away: every model reads as not measured.
        LOGGER.warning("capability list unavailable: %s", error)
        return CapabilityList(
            schema_version=SCHEMA_VERSION, provisional=True, source="", models=[]
        )


@lru_cache
def _by_key() -> dict[str, MeasuredModel]:
    return {key: row for row in measured_list().models for key in row.match.keys}


def find_row(key: str) -> MeasuredModel | None:
    return _by_key().get(key)
