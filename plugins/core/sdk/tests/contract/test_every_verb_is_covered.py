import importlib.util
import inspect
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest

import surfsense_plugin_sdk

# With the unit tests, so a pull request that adds a verb fails the SDK's own
# check until it adds the verb's contract test too.
pytestmark = pytest.mark.unit

CONTRACT_TESTS = Path(__file__).parent


def _public_verbs() -> Iterator[str]:
    """Each function a plugin can call on the app, such as document.add."""
    for name in surfsense_plugin_sdk.__all__:
        module = getattr(surfsense_plugin_sdk, name)
        if not (
            isinstance(module, ModuleType)
            and module.__name__.startswith(f"{surfsense_plugin_sdk.__name__}.app.")
        ):
            continue
        domain = module.__name__.rsplit(".", 1)[1]
        for verb, thing in vars(module).items():
            if (
                inspect.isfunction(thing)
                and thing.__module__ == module.__name__
                and not verb.startswith("_")
            ):
                yield f"{domain}.{verb}"


def _contract_tests() -> Iterator[Callable[..., object]]:
    """Every test function in the contract test files, read without running them."""
    for path in CONTRACT_TESTS.glob("test_*.py"):
        if path == Path(__file__):
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield from (
            thing
            for name, thing in vars(module).items()
            if name.startswith("test_") and inspect.isfunction(thing)
        )


def test_every_public_verb_has_a_contract_test() -> None:
    """A verb no contract test calls is one the app could break without anyone seeing."""
    covered = {
        mark.args[0]
        for test in _contract_tests()
        for mark in getattr(test, "pytestmark", [])
        if mark.name == "covers"
    }

    assert set(_public_verbs()) - covered == set()
