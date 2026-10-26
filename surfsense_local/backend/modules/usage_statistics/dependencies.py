"""What the summary reads off this machine rather than the database, as one dependency a test replaces."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import psutil
from fastapi import Depends

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.hardware import SystemInventory
from modules.usage_statistics.ui_language import ui_language
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MachineReadings:
    inventory: Callable[[], SystemInventory | None]
    ram_total_bytes: Callable[[], int | None]
    holds_local_model: Callable[[str], bool]
    ui_language: Callable[[], str]


def get_machine_readings() -> MachineReadings:
    return MachineReadings(
        inventory=_inventory,
        ram_total_bytes=_ram_total_bytes,
        holds_local_model=lambda name: (
            get_local_catalog().engine_holding(name) is not None
        ),
        ui_language=lambda: ui_language(get_storage_settings().data_dir / "electron"),
    )


def _inventory() -> SystemInventory | None:
    """The catalog's probe, taken once per process; the first waits for it."""
    try:
        return get_local_catalog().inventory()
    except Exception:
        logger.warning(
            "could not read the devices for the usage summary", exc_info=True
        )
        return None


def _ram_total_bytes() -> int | None:
    try:
        return psutil.virtual_memory().total
    except (OSError, RuntimeError):
        return None


MachineReadingsDep = Annotated[MachineReadings, Depends(get_machine_readings)]
