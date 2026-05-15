"""Registry + auto-discovery tests.

* Auto-discovery skips packages starting with ``_`` (so test fixtures
  don't leak into the production catalogue).
* Manually importing a ``_demo`` benchmark fires its ``register(...)``
  call and the CLI sees it.
"""

from __future__ import annotations

import importlib

from surfsense_evals.core import registry


def _force_register_demo() -> None:
    """Import (or reload) the demo module so its ``register(...)`` runs.

    On a fresh interpreter, ``import_module`` triggers package
    initialization. After the first call though, the module is cached
    in ``sys.modules`` and a second ``import_module`` is a no-op — so
    if a previous test already unregistered the entry, we have to
    ``reload`` to re-execute the module body.
    """

    module = importlib.import_module("surfsense_evals.suites._demo.hello")
    if ("_demo", "hello") not in registry.snapshot():
        importlib.reload(module)


def test_auto_discovery_skips_underscore_prefixed_subpackages():
    from surfsense_evals.suites import discover_suites

    discovered = discover_suites()
    assert all(not part.startswith("_") for full in discovered for part in full.split("."))
    # The medical suite's headline benchmark must always discover.
    assert any(name.endswith(".medical.medxpertqa") for name in discovered)


def test_demo_benchmark_registers_on_explicit_import():
    _force_register_demo()
    bench = registry.get("_demo", "hello")
    assert bench is not None
    assert bench.name == "hello"
    assert bench.headline is False
    # Cleanup so the test is idempotent under repeated runs.
    registry.unregister("_demo", "hello")


def test_register_unregister_roundtrip():
    # Make sure no stale entry from a prior test in the session.
    if ("_demo", "hello") in registry.snapshot():
        registry.unregister("_demo", "hello")
    snapshot_before = dict(registry.snapshot())
    _force_register_demo()
    assert ("_demo", "hello") in registry.snapshot()
    registry.unregister("_demo", "hello")
    assert dict(registry.snapshot()) == snapshot_before
