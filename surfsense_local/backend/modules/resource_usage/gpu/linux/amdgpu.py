"""AMD cards through amdgpu's sysfs files, each process's share through DRM fdinfo.

fdinfo is read only for the app's own processes and only for descriptors open on
/dev/dri, so the cost follows the app rather than the machine.
"""

import os
from collections.abc import Callable, Set
from dataclasses import dataclass
from pathlib import Path

from modules.resource_usage.gpu.carve_out import is_carve_out
from modules.resource_usage.gpu.reading import GpuReading

_UNITS = {"KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}


@dataclass(frozen=True)
class _Card:
    device: Path
    slot: str
    name: str


def _pci_slot(device: Path) -> str:
    """The PCI address fdinfo's drm-pdev names: the device link's last part."""
    return Path(os.path.realpath(device)).name


class AmdgpuReader:
    def __init__(
        self,
        drm: Path = Path("/sys/class/drm"),
        proc: Path = Path("/proc"),
        *,
        fd_target: Callable[[Path], str] = os.readlink,
        slot_of: Callable[[Path], str] = _pci_slot,
    ) -> None:
        self._proc = proc
        self._fd_target = fd_target
        self._cards = [
            _Card(device, slot_of(device).strip(), _product_name(device))
            for device in _devices(drm)
            if not is_carve_out(_number(device / "mem_info_vram_total") or 0)
        ]

    @property
    def found(self) -> bool:
        return bool(self._cards)

    def read(self, pids: Set[int]) -> list[GpuReading]:
        shares = self._shares(pids)
        return [
            GpuReading(
                name=card.name,
                total_bytes=_number(card.device / "mem_info_vram_total") or 0,
                used_bytes=_number(card.device / "mem_info_vram_used") or 0,
                busy_percent=_float(_number(card.device / "gpu_busy_percent")),
                process_bytes=shares.get(card.slot, {}),
            )
            for card in self._cards
        ]

    def _shares(self, pids: Set[int]) -> dict[str, dict[int, int]]:
        """Card slot to pid to bytes. A dup'd descriptor is one client, counted once."""
        shares: dict[str, dict[int, int]] = {}
        for pid in pids:
            seen: set[tuple[str, str]] = set()
            for fd in _entries(self._proc / str(pid) / "fd"):
                try:
                    if not self._fd_target(fd).startswith("/dev/dri/"):
                        continue
                    fields = _fields(
                        (self._proc / str(pid) / "fdinfo" / fd.name).read_text()
                    )
                except OSError:
                    continue
                slot, client = fields.get("drm-pdev"), fields.get("drm-client-id")
                vram = _bytes(fields.get("drm-memory-vram"))
                if (
                    slot is None
                    or client is None
                    or vram is None
                    or (slot, client) in seen
                ):
                    continue
                seen.add((slot, client))
                per_pid = shares.setdefault(slot, {})
                per_pid[pid] = per_pid.get(pid, 0) + vram
        return shares


def _devices(drm: Path) -> list[Path]:
    """cardN only: card0-DP-1 is a connector and renderD128 the same device again."""
    return [
        entry / "device"
        for entry in sorted(_entries(drm))
        if entry.name.startswith("card")
        and entry.name[4:].isdigit()
        and (entry / "device" / "mem_info_vram_total").is_file()
    ]


def _entries(folder: Path) -> list[Path]:
    try:
        return list(folder.iterdir())
    except OSError:
        return []


def _product_name(device: Path) -> str:
    try:
        return (device / "product_name").read_text().strip() or "AMD GPU"
    except OSError:
        return "AMD GPU"


def _number(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _float(value: int | None) -> float | None:
    return None if value is None else float(value)


def _fields(text: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def _bytes(value: str | None) -> int | None:
    """ "4096 KiB" as the kernel writes it; a bare number is bytes."""
    if value is None:
        return None
    number, _, unit = value.partition(" ")
    try:
        return int(number) * _UNITS.get(unit.strip(), 1)
    except ValueError:
        return None
