"""Use a LibreOffice the user already has, once they confirm it in Settings."""

import time
from collections.abc import Callable, Iterable
from pathlib import Path

from modules.runtime_packs.office import records
from modules.runtime_packs.office.detect import find_installed
from modules.runtime_packs.office.runtime import OfficeRuntime
from modules.runtime_packs.office.smoke import SMOKE_SECONDS, smoke_test
from modules.runtime_packs.office.soffice.version import report_version


class ConfirmRefusedError(Exception):
    """`code` is not_found, a detect refusal, or smoke_failed."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def confirm_installed(
    *,
    candidates: Iterable[Path] | None = None,
    smoke: Callable[[OfficeRuntime], None] = smoke_test,
    version_of: Callable[[OfficeRuntime], str] | None = None,
) -> records.ConfirmedRecord:
    """Vet the install found at a fixed location, run the smoke, and record it."""
    found = find_installed(candidates)
    if found is None:
        raise ConfirmRefusedError("not_found")
    if found.refusal is not None:
        raise ConfirmRefusedError(found.refusal)
    runtime = OfficeRuntime(found.program, found.branch, "installed")
    try:
        version = (version_of or _version_of)(runtime)
        smoke(runtime)
    except Exception as error:
        raise ConfirmRefusedError("smoke_failed", str(error)) from error
    record = records.ConfirmedRecord(str(found.root), version, found.branch)
    records.write_confirmed(record)
    return record


def _version_of(runtime: OfficeRuntime) -> str:
    return report_version(runtime, deadline=time.monotonic() + SMOKE_SECONDS)
