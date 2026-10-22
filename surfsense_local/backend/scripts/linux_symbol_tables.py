"""Strip symbol tables from a frozen bundle's ELF files on Linux.

The loader reads only the dynamic symbols; the full tables only name internal
functions in native crash traces, and they are a fifth of the backend.

Libraries auditwheel vendored are left alone: patchelf rewrote their program
headers, and strip then leaves them unloadable ("ELF load command
address/offset not page-aligned", numpy's OpenBLAS, 22 Oct 2026).
auditwheel puts them in a `<package>.libs` folder and hashes their names.
"""

import re
import subprocess
from pathlib import Path

_ELF_MAGIC = b"\x7fELF"
_AUDITWHEEL_NAME = re.compile(r"-[0-9a-f]{8}\.so")


def _is_elf(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(4) == _ELF_MAGIC


def _vendored_by_auditwheel(path: Path) -> bool:
    return any(part.endswith(".libs") for part in path.parts) or bool(
        _AUDITWHEEL_NAME.search(path.name)
    )


def strip_symbol_tables(internal: Path) -> int:
    """Strip every ELF file under `internal` but auditwheel's; returns how many.

    Never the bootloader beside `internal`, which carries its archive appended.
    """
    count = 0
    for path in sorted(internal.rglob("*")):
        if path.is_symlink() or not path.is_file() or _vendored_by_auditwheel(path):
            continue
        if not _is_elf(path):
            continue
        subprocess.run(["strip", "--strip-unneeded", str(path)], check=True)
        count += 1
    return count
