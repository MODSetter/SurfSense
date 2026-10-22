"""Strip symbol tables from a frozen bundle's ELF files on Linux.

The loader reads only the dynamic symbols; the full tables only name internal
functions in native crash traces, and they are a fifth of the backend.

strip can leave a library that patchelf rewrote unloadable ("ELF load command
address/offset not page-aligned": numpy's OpenBLAS and torchvision's
image_stable.so, 22 Oct 2026). Each file is stripped as a copy, and the copy
replaces it only when every loadable segment still passes the check glibc
makes; otherwise the file ships unstripped.
"""

import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

_ELF_MAGIC = b"\x7fELF"
_PT_LOAD = 1
_PAGE = 4096


def _is_elf(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(4) == _ELF_MAGIC


def loads_aligned(elf: bytes) -> bool:
    """Every PT_LOAD's vaddr and offset agree mod the page and its own alignment.

    glibc refuses the page case outright and newer versions the alignment one;
    a copy that fails either is simply not used.
    """
    if elf[:4] != _ELF_MAGIC or elf[4] != 2 or elf[5] != 1:
        return False  # only 64-bit little-endian is built here
    (phoff,) = struct.unpack_from("<Q", elf, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x36)
    for index in range(phnum):
        header = phoff + index * phentsize
        (p_type,) = struct.unpack_from("<I", elf, header)
        if p_type != _PT_LOAD:
            continue
        p_offset, p_vaddr = struct.unpack_from("<QQ", elf, header + 8)
        (p_align,) = struct.unpack_from("<Q", elf, header + 48)
        if (p_vaddr - p_offset) % _PAGE:
            return False
        if p_align > 1 and (p_align % _PAGE or (p_vaddr - p_offset) % p_align):
            return False
    return True


def strip_symbol_tables(internal: Path) -> tuple[int, list[Path]]:
    """Strip every ELF file under `internal` that stays loadable.

    Returns how many were stripped and which were kept as they were. Never
    the bootloader beside `internal`, which carries its archive appended.
    """
    stripped, kept = 0, []
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / "elf"
        for path in sorted(internal.rglob("*")):
            if path.is_symlink() or not path.is_file() or not _is_elf(path):
                continue
            shutil.copy2(path, copy)
            subprocess.run(["strip", "--strip-unneeded", str(copy)], check=True)
            if loads_aligned(copy.read_bytes()):
                shutil.copy2(copy, path)
                stripped += 1
            else:
                kept.append(path)
    return stripped, kept
