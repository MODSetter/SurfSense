"""Bounded access to untrusted OOXML ZIP packages."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Set
from contextlib import contextmanager
from io import BytesIO
from zipfile import BadZipFile, ZipFile

MAX_ZIP_ENTRIES = 10_000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class OoxmlError(ValueError):
    """A stable, user-actionable OOXML structural finding."""


@contextmanager
def open_ooxml(
    data: bytes,
    *,
    format_name: str,
    required_parts: Set[str],
    part_limits: Mapping[str, int] | None = None,
) -> Iterator[ZipFile]:
    """Validate package-level limits before yielding an OOXML archive."""
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            entry_names = [entry.filename for entry in entries]
            names = set(entry_names)
            if len(entries) > MAX_ZIP_ENTRIES:
                raise OoxmlError(
                    f"{format_name} contains more than {MAX_ZIP_ENTRIES} ZIP entries"
                )
            if len(names) != len(entry_names):
                raise OoxmlError(f"{format_name} contains duplicate OOXML parts")
            missing = sorted(required_parts - names)
            if missing:
                raise OoxmlError(
                    f"{format_name} is missing required parts: {', '.join(missing)}"
                )
            if any(entry.flag_bits & 1 for entry in entries):
                raise OoxmlError(f"{format_name} contains encrypted ZIP entries")
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                raise OoxmlError(
                    f"{format_name} uncompressed content exceeds "
                    f"{MAX_UNCOMPRESSED_BYTES} bytes"
                )
            for part, limit in (part_limits or {}).items():
                if archive.getinfo(part).file_size > limit:
                    label = part.rsplit("/", 1)[-1].replace(".xml", " XML")
                    raise OoxmlError(f"{format_name} {label} exceeds {limit} bytes")
            yield archive
    except OoxmlError:
        raise
    except (BadZipFile, KeyError, OSError, RuntimeError):
        raise OoxmlError(f"{format_name} is not valid OOXML") from None
