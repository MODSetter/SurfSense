"""Which LibreOffice runs a conversion: the Office pack, then the user's confirmed one."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from modules.runtime_packs.office import layout, records
from modules.runtime_packs.office.detect import vet
from modules.runtime_packs.office.program import program_in
from modules.runtime_packs.office.soffice.errors import OfficeMissing


@dataclass(frozen=True)
class OfficeRuntime:
    program: Path
    version: str
    source: Literal["pack", "installed"]


@dataclass(frozen=True)
class OfficeUnavailable:
    """`reason` is not_installed, or why the confirmed install can no longer run."""

    reason: str


def office_runtime() -> OfficeRuntime | OfficeUnavailable:
    pack = records.read_pack()
    if pack is not None:
        program = program_in(layout.versions_dir() / pack.root)
        if program.is_file():
            return OfficeRuntime(program, pack.version, "pack")
    confirmed = records.read_confirmed()
    if confirmed is None:
        return OfficeUnavailable("not_installed")
    # Checked again each time: an update may have moved it to an ended branch.
    found = vet(Path(confirmed.root))
    if found.refusal is not None:
        return OfficeUnavailable(found.refusal)
    return OfficeRuntime(found.program, confirmed.version, "installed")


def require_runtime() -> OfficeRuntime:
    """office_runtime(), raising OfficeMissing with its reason when there is none."""
    found = office_runtime()
    if isinstance(found, OfficeUnavailable):
        raise OfficeMissing(found.reason)
    return found
