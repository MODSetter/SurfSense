"""Strip local symbols from a frozen bundle's Mach-O files on macOS.

`strip -x` keeps every external symbol, which is all dyld and dlsym read; the
local ones only name static functions in crash traces, and they are 175 MB of
the backend. PyInstaller's own strip (-S) removes 10. arm64 macOS runs only
signed code, so each file is signed again, ad hoc: electron-builder signs it
for real when it packages the app.
"""

import subprocess
from pathlib import Path

# 64-bit Mach-O in either byte order, and universal (fat) files.
_MACH_O_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"}


def _is_mach_o(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(4) in _MACH_O_MAGIC


def strip_local_symbols(internal: Path) -> int:
    """Strip and re-sign every Mach-O under `internal`; returns how many.

    Never the bootloader beside `internal`: its archive sits inside
    __LINKEDIT, and strip would cut it.
    """
    count = 0
    for path in sorted(internal.rglob("*")):
        if path.is_symlink() or not path.is_file() or not _is_mach_o(path):
            continue
        subprocess.run(["strip", "-x", str(path)], check=True)
        subprocess.run(["codesign", "--force", "--sign", "-", str(path)], check=True)
        count += 1
    return count
