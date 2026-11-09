"""The modules the API role must not import, listed at build time.

The API used to be its own binary, so it could import only what its own
analysis collected. One bundle now carries the worker's modules too; this lists
the difference so frozen_entry.py can hide it from the API role and the API
behaves exactly as that binary did.
"""

import re
from pathlib import Path

_EXTENSION_SUFFIX = re.compile(r"(\.(cp\d+|cpython)[^.]*|\.abi3)?\.(pyd|so)$")
# Folders PyInstaller puts on sys.path, so what is inside imports by its own
# name: the stdlib's extensions on Linux and macOS, and pywin32's modules.
_ON_SYS_PATH = re.compile(r"^(python\d+\.\d+/lib-dynload|win32/lib|win32|pythonwin)/")
# main.py is the API-only analysis's script, so it is not among that
# analysis's modules, while the bundle imports it as one.
_API_ENTRY = {"main"}


def _module_names(analysis) -> set[str]:
    """Modules as bytecode, as native extensions, and as source shipped as data:
    some hooks collect a package only as .py files (cv2 loads itself that way)."""
    names = {name for name, _, _ in analysis.pure}
    for destination, _, typecode in analysis.binaries:
        if typecode == "EXTENSION":
            module = _EXTENSION_SUFFIX.sub("", _importable(destination))
            names.add(module.replace("/", "."))
    for destination, _, _ in analysis.datas:
        path = _importable(destination)
        if path.endswith(".py"):
            module = path.removesuffix(".py").removesuffix("/__init__")
            names.add(module.replace("/", "."))
    return names


def _importable(destination: str) -> str:
    """The destination relative to the sys.path entry it imports from."""
    return _ON_SYS_PATH.sub("", destination.replace("\\", "/"))


def _outermost(names: set[str]) -> list[str]:
    """Drop every name whose package is already listed: hiding it hides them."""
    kept: list[str] = []
    for name in sorted(names, key=lambda n: (n.count("."), n)):
        parts = name.split(".")
        if not any(".".join(parts[:i]) in names for i in range(1, len(parts))):
            kept.append(name)
    return sorted(kept)


def write_api_absent_modules(api_only, bundle, out: Path) -> Path:
    """Write the bundle's modules an API-only analysis did not collect."""
    absent = _module_names(bundle) - _module_names(api_only) - _API_ENTRY
    out.write_text("\n".join(_outermost(absent)) + "\n")
    return out
