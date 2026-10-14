"""What is installed, written by one process and read by every other.

Files, not database rows: the workers that run LibreOffice read them without a
session, and a record is replaced in one rename.
"""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from modules.runtime_packs.office import layout


@dataclass(frozen=True)
class PackRecord:
    """The unpacked version in use; `root` is relative to the versions folder."""

    version: str
    root: str


@dataclass(frozen=True)
class ConfirmedRecord:
    """The user's own LibreOffice, as it was when they confirmed it."""

    root: str
    version: str
    branch: str


def read_pack() -> PackRecord | None:
    return _read(layout.installed_record(), PackRecord)


def write_pack(record: PackRecord | None) -> None:
    _write(layout.installed_record(), record)
    if record is not None:
        write_offer_dismissed()


def read_confirmed() -> ConfirmedRecord | None:
    return _read(layout.confirmed_record(), ConfirmedRecord)


def write_confirmed(record: ConfirmedRecord | None) -> None:
    _write(layout.confirmed_record(), record)
    if record is not None:
        write_offer_dismissed()


@dataclass(frozen=True)
class OfferDismissed:
    """Turned on once, or the offer dismissed: it is not offered again on this install."""

    dismissed: bool = True


def read_offer_dismissed() -> bool:
    return _read(layout.offer_dismissed_record(), OfferDismissed) is not None


def write_offer_dismissed() -> None:
    _write(layout.offer_dismissed_record(), OfferDismissed())


def _read[T](path: Path, kind: type[T]) -> T | None:
    try:
        return kind(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def _write(path: Path, record: object | None) -> None:
    if record is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f"{path.name}.{os.getpid()}")
    staged.write_text(json.dumps(asdict(record)), encoding="utf-8")
    staged.replace(path)
