"""Suite registry auto-discovery.

Importing ``surfsense_evals.suites`` walks every subpackage one level deep
(domain like ``medical``) AND its benchmark subpackages
(``medical/medxpertqa``, ``medical/mirage``, ``medical/cure``). Each
benchmark's ``__init__.py`` is expected to call
``core.registry.register(<Benchmark>)`` at module bottom; merely importing
the module is enough to populate the registry.

Adding a new domain is therefore: drop a folder under ``suites/`` with the
right structure. No edits anywhere else.

Subpackages whose name starts with ``_`` are skipped — that's reserved for
test fixtures (e.g. ``suites/_demo/``) so they don't accidentally show up
in ``benchmarks list``.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Iterable

logger = logging.getLogger(__name__)


def _iter_subpackages(package) -> Iterable[str]:
    """Yield fully-qualified subpackage names one level deep, skipping ``_*``."""

    for module_info in pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."):
        if not module_info.ispkg:
            continue
        leaf = module_info.name.rsplit(".", 1)[-1]
        if leaf.startswith("_"):
            continue
        yield module_info.name


def discover_suites() -> list[str]:
    """Import every domain + benchmark subpackage so registrations fire.

    Returns the list of fully-qualified benchmark module names that were
    successfully imported. Failures are logged (not raised) so a single
    broken benchmark doesn't take down the whole CLI — the operator still
    sees the working benchmarks via ``benchmarks list``.
    """

    import surfsense_evals.suites as _suites  # self-import for __path__

    imported: list[str] = []
    for domain_name in _iter_subpackages(_suites):
        try:
            domain_pkg = importlib.import_module(domain_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to import suite domain %s: %s", domain_name, exc)
            continue
        for benchmark_name in _iter_subpackages(domain_pkg):
            try:
                importlib.import_module(benchmark_name)
                imported.append(benchmark_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to import benchmark %s: %s", benchmark_name, exc
                )
    return imported
