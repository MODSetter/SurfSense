"""Pre-register the etl_pipeline package to avoid circular imports during unit tests."""

import sys
import types
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]


def _stub_package(dotted: str, fs_dir: Path) -> None:
    if dotted not in sys.modules:
        mod = types.ModuleType(dotted)
        mod.__path__ = [str(fs_dir)]
        mod.__package__ = dotted
        sys.modules[dotted] = mod

    parts = dotted.split(".")
    if len(parts) > 1:
        parent_dotted = ".".join(parts[:-1])
        parent = sys.modules.get(parent_dotted)
        if parent is not None:
            setattr(parent, parts[-1], sys.modules[dotted])


_stub_package("app", _BACKEND / "app")
_stub_package("app.etl_pipeline", _BACKEND / "app" / "etl_pipeline")
_stub_package("app.etl_pipeline.parsers", _BACKEND / "app" / "etl_pipeline" / "parsers")
