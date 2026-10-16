"""SurfSense ships no Claude Code (ADR 0057).

The Agent SDK's wheel carries one, `claude_agent_sdk/_bundled/claude`, 241 MB.
PyInstaller packs the SDK's Python but not that file, because nothing asks for
the SDK's data. One `collect_all("claude_agent_sdk")` would ship it silently, so
this reads every spec the way PyInstaller does and refuses any call that names
the SDK.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

BACKEND = Path(__file__).resolve().parents[2]
SPECS = sorted((BACKEND / "bundling").glob("*.spec"))
# PyInstaller's helpers that copy a package's files, not only its Python.
COLLECTORS = {
    "collect_all",
    "collect_data_files",
    "collect_dynamic_libs",
    "copy_metadata",
}


def collected_packages(spec: Path) -> set[str]:
    """Every package a spec hands to a collector by name."""
    found = set()
    for node in ast.walk(ast.parse(spec.read_text())):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) in COLLECTORS
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            found.add(str(node.args[0].value))
    return found


def test_the_spec_reader_sees_a_collector() -> None:
    """So an empty answer below means none, not a reader that cannot see one."""
    assert "onnxruntime" in collected_packages(BACKEND / "bundling" / "api.spec")


@pytest.mark.parametrize("spec", SPECS, ids=lambda p: p.name)
def test_no_spec_collects_the_agent_sdks_files(spec: Path) -> None:
    """Collecting them would ship the SDK's own Claude Code."""
    collected = {
        name for name in collected_packages(spec) if name.startswith("claude_agent_sdk")
    }

    assert collected == set(), f"{spec.name} would ship Claude Code: {collected}"
