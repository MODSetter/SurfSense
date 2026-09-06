import json
from pathlib import Path

import pytest

from modules.llm.recommendations.llmfit import LlmfitAdvisor
from modules.llm.recommendations.types import FitLevel

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parents[3] / "fixtures" / "llmfit"


def _executable(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "llmfit"
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(0o755)
    return path


async def test_adapter_normalizes_the_pinned_cli_contract(tmp_path: Path) -> None:
    """CLI labels, null estimates, and future fields normalize at one seam."""
    system = json.dumps(json.loads((FIXTURES / "system.json").read_text()))
    fit = json.dumps(json.loads((FIXTURES / "fit.json").read_text()))
    executable = _executable(
        tmp_path,
        f"""
import sys
if "--version" in sys.argv:
    print("llmfit 1.1.11")
elif "system" in sys.argv:
    print({system!r})
else:
    print({fit!r})
""",
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 2).scan(8192)

    assert result.warnings == ()
    assert result.system is not None
    assert result.system.unified_memory is True
    assert [model.fit for model in result.models] == [
        FitLevel.GOOD,
        FitLevel.PERFECT,
    ]
    assert result.models[0].publisher == "Qwen"
    assert result.models[0].prefill_tps is None
    assert result.models[0].capability_ids == ("tool_use",)


async def test_missing_binary_degrades_to_a_warning(tmp_path: Path) -> None:
    """A missing optional advisor cannot prevent the API from starting."""
    result = await LlmfitAdvisor(tmp_path / "missing", "1.1.11", 1).scan(8192)

    assert result.models == ()
    assert result.warnings[0].code == "missing"


async def test_version_drift_refuses_to_parse_unknown_output(tmp_path: Path) -> None:
    """A binary upgrade requires fixture review before recommendations resume."""
    executable = _executable(tmp_path, 'print("llmfit 2.0.0")\n')

    result = await LlmfitAdvisor(executable, "1.1.11", 1).scan(8192)

    assert result.models == ()
    assert result.warnings[0].code == "version_mismatch"


async def test_timeout_kills_the_process(tmp_path: Path) -> None:
    """A hung hardware probe returns promptly instead of leaking a child."""
    executable = _executable(
        tmp_path,
        "import time\ntime.sleep(10)\n",
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 0.01).scan(8192)

    assert result.warnings[0].code == "timeout"


async def test_malformed_json_is_not_partially_accepted(tmp_path: Path) -> None:
    """Malformed advisor output returns no recommendations."""
    executable = _executable(
        tmp_path,
        """
import sys
print("llmfit 1.1.11" if "--version" in sys.argv else "{not-json")
""",
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 1).scan(8192)

    assert result.models == ()
    assert result.warnings[0].code == "invalid_output"


async def test_nonzero_exit_is_a_scan_warning(tmp_path: Path) -> None:
    """Advisor diagnostics stay in logs while the public API gets a safe warning."""
    executable = _executable(
        tmp_path,
        'import sys\nprint("probe failed", file=sys.stderr)\nsys.exit(2)\n',
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 1).scan(8192)

    assert result.models == ()
    assert result.warnings[0].code == "scan_failed"
