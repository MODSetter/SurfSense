"""The one frozen binary picks its role from its arguments, and never a default."""

import importlib.util
import sys

import pytest

import frozen_entry

pytestmark = pytest.mark.unit


@pytest.fixture
def roles(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    """Each role started, in order, instead of starting it."""
    started: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        frozen_entry, "_api", lambda args: started.append(("api", args))
    )
    monkeypatch.setattr(
        frozen_entry, "_worker", lambda args: started.append(("worker", args))
    )
    return started


@pytest.mark.parametrize(
    ("arguments", "role"),
    [
        (["api"], ("api", [])),
        (["worker", "ingest"], ("worker", ["ingest"])),
        (["worker", "studio"], ("worker", ["studio"])),
        # The shapes the app re-runs its own binary with, unchanged.
        (["--probe-devices", "lib"], ("api", ["--probe-devices", "lib"])),
        (["--check-retrieval-runtime"], ("api", ["--check-retrieval-runtime"])),
        (["--run-document-script", "d"], ("worker", ["--run-document-script", "d"])),
        (["--decode-audio", "a", "b"], ("worker", ["--decode-audio", "a", "b"])),
        (["--check-scan-ocr"], ("worker", ["--check-scan-ocr"])),
        (["--check-vision-runtime"], ("worker", ["--check-vision-runtime"])),
    ],
)
def test_each_launch_reaches_its_role(
    roles: list[tuple[str, list[str]]],
    arguments: list[str],
    role: tuple[str, list[str]],
) -> None:
    """Roles by name, and the self-run flags in the shapes callers already use."""
    frozen_entry.dispatch(arguments)

    assert roles == [role]


@pytest.mark.parametrize(
    "arguments", [[], ["serve"], ["worker"], ["api", "extra"], ["-S", "-m", "x"]]
)
def test_a_launch_without_a_role_exits_without_starting_one(
    roles: list[tuple[str, list[str]]], arguments: list[str]
) -> None:
    """A stray launch must not start a server that nothing is waiting on."""
    with pytest.raises(SystemExit) as exited:
        frozen_entry.dispatch(arguments)

    assert exited.value.code == 2
    assert roles == []


def test_a_hidden_module_looks_absent(tmp_path) -> None:
    """As in a binary that never carried it: no spec, and ModuleNotFoundError."""
    names = ["this", "json.tool"]
    assert not any(name in sys.modules for name in names)
    listing = tmp_path / "absent.txt"
    listing.write_text("\n".join(names))

    hidden = frozen_entry.hide_worker_only_modules(listing)
    try:
        assert hidden == names
        assert importlib.util.find_spec("this") is None
        with pytest.raises(ModuleNotFoundError):
            import this  # noqa: F401
        with pytest.raises(ModuleNotFoundError):
            import json.tool  # noqa: F401
    finally:
        for name in hidden:
            del sys.modules[name]


def test_an_already_imported_module_is_left_alone(tmp_path) -> None:
    """Hiding never pulls a module out from under code that holds it."""
    listing = tmp_path / "absent.txt"
    listing.write_text("json\n")

    assert frozen_entry.hide_worker_only_modules(listing) == []
    assert sys.modules["json"] is not None
