"""What these packages import of each other must not depend on which loads first."""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "module",
    [
        "modules.llm.connections",
        "modules.llm.connections.key_headers",
        "modules.llm.connections.service",
        "modules.llm.connections.serves",
        "modules.llm.providers",
        "modules.llm.providers.openai_compatible.speech",
        "modules.llm.providers.openai_compatible.published_voices",
        "modules.llm.voices.roster",
    ],
)
def test_a_module_can_be_the_first_one_imported(module: str) -> None:
    """In a fresh process, since a test run has already loaded them all in some order."""
    run = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr[-400:]
