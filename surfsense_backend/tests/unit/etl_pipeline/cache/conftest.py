"""Stub the cache package __init__s so unit tests import only pure leaf modules.

The real ``cache``/``storage``/``eviction``/``persistence`` __init__s eagerly
import the facade, file storage, Celery, and ``app.db`` -- none of which a pure
unit test should need. Turning those packages into bare namespace packages lets
``from app.etl_pipeline.cache.<pkg>.<leaf> import ...`` resolve the leaf module
without running the heavy __init__. ``schemas`` is left real (it is pure).
"""

import sys
import types
from pathlib import Path

_CACHE_DIR = Path(__file__).resolve().parents[4] / "app" / "etl_pipeline" / "cache"


def _stub_namespace_package(dotted: str, fs_dir: Path) -> None:
    if dotted in sys.modules:
        return
    module = types.ModuleType(dotted)
    module.__path__ = [str(fs_dir)]
    module.__package__ = dotted
    sys.modules[dotted] = module


_stub_namespace_package("app.etl_pipeline.cache", _CACHE_DIR)
_stub_namespace_package("app.etl_pipeline.cache.storage", _CACHE_DIR / "storage")
_stub_namespace_package("app.etl_pipeline.cache.eviction", _CACHE_DIR / "eviction")
