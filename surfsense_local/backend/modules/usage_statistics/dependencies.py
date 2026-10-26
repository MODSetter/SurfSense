"""What the summary reads off this machine rather than the database, as one dependency a test replaces."""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated

import psutil
from fastapi import Depends

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.hardware import SystemInventory, os_adapter_names
from modules.usage_statistics.ui_language import ui_language
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MachineReadings:
    inventory: Callable[[], SystemInventory | None]
    os_adapter_names: Callable[[], Sequence[str] | None]
    ram_total_bytes: Callable[[], int | None]
    holds_local_model: Callable[[str], bool]
    ui_language: Callable[[], str]


def get_machine_readings() -> MachineReadings:
    return MachineReadings(
        inventory=_inventory,
        os_adapter_names=_os_adapter_names,
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


class _OsAdapterNames:
    """Asked once per process once it answers: on Windows each ask starts PowerShell.

    A failed ask is tried again an hour later, not on every five-minute summary,
    so one bad moment does not leave the card's maker unknown all session.
    """

    def __init__(self) -> None:
        self.cache_clear()

    def cache_clear(self) -> None:
        self._names: tuple[str, ...] | None = None
        self._failed_at: float | None = None

    def __call__(self) -> tuple[str, ...] | None:
        if self._names is not None:
            return self._names
        now = _monotonic()
        if (
            self._failed_at is not None
            and now - self._failed_at < _RETRY_FAILED_SECONDS
        ):
            return None
        try:
            names = os_adapter_names()
        except Exception:
            logger.warning(
                "could not list the graphics adapters for the usage summary",
                exc_info=True,
            )
            names = None
        if names is None:
            self._failed_at = now
            return None
        self._names = tuple(names)
        return self._names


_RETRY_FAILED_SECONDS = 3600.0
_monotonic = time.monotonic
_os_adapter_names = _OsAdapterNames()


def _ram_total_bytes() -> int | None:
    try:
        return psutil.virtual_memory().total
    except (OSError, RuntimeError):
        return None


MachineReadingsDep = Annotated[MachineReadings, Depends(get_machine_readings)]
