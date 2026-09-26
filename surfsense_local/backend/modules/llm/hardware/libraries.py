"""Loading ggml through ctypes.

Two handles on Windows, one everywhere else. The exported symbols are split
across `ggml` and `ggml-base`, and PE exports do not chain, so a single
`CDLL("ggml.dll")` raises AttributeError on the first device query. ELF and
Mach-O resolve the second library through their own dependency records, where
the opposite is true: `CDLL("libggml-base.so")` cannot see `load_all`.
"""

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GgmlLibraries:
    """`core` registers backends and counts devices; `base` describes them."""

    core: ctypes.CDLL
    base: ctypes.CDLL


def _candidates(stem: str) -> tuple[str, ...]:
    if sys.platform == "win32":
        return (f"{stem}.dll",)
    if sys.platform == "darwin":
        return (f"lib{stem}.dylib",)
    return (f"lib{stem}.so",)


def _load(directory: Path, stem: str) -> ctypes.CDLL:
    errors = []
    for name in _candidates(stem):
        try:
            return ctypes.CDLL(str(directory / name))
        except OSError as error:
            errors.append(f"{name}: {error}")
    raise OSError(f"could not load {stem} from {directory}: {'; '.join(errors)}")


def load(directory: Path) -> GgmlLibraries:
    """Open ggml from a staged directory and declare the signatures we call."""
    core = _load(directory, "ggml")
    base = core if sys.platform != "win32" else _load(directory, "ggml-base")

    core.ggml_backend_load_all.restype = None
    core.ggml_backend_dev_count.restype = ctypes.c_size_t
    core.ggml_backend_dev_get.restype = ctypes.c_void_p
    core.ggml_backend_dev_get.argtypes = [ctypes.c_size_t]

    for name in ("name", "description"):
        fn = getattr(base, f"ggml_backend_dev_{name}")
        fn.restype = ctypes.c_char_p
        fn.argtypes = [ctypes.c_void_p]

    base.ggml_backend_dev_type.restype = ctypes.c_int
    base.ggml_backend_dev_type.argtypes = [ctypes.c_void_p]
    base.ggml_backend_dev_memory.restype = None
    base.ggml_backend_dev_memory.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    return GgmlLibraries(core=core, base=base)
