"""Tests that run the user's own Claude Code on their plan.

Skipped unless SURFSENSE_CLAUDE_CODE_TESTS=1 and Claude Code is installed and
signed in, so CI and ordinary runs never touch anyone's plan.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from modules.llm.subscriptions.claude.locate import locate_claude
from modules.llm.subscriptions.claude.status import ClaudeState, read_status


@pytest.fixture(scope="session")
def claude_binary() -> Iterator[Path]:
    """The signed-in Claude Code these tests run, or a skip."""
    if os.environ.get("SURFSENSE_CLAUDE_CODE_TESTS") != "1":
        pytest.skip("set SURFSENSE_CLAUDE_CODE_TESTS=1 to run the real Claude Code")
    binary = locate_claude(path_env=os.environ.get("PATH"), home=Path.home())
    if read_status(binary).state is not ClaudeState.READY:
        pytest.skip("Claude Code is not installed and signed in to a plan")
    assert binary is not None
    yield binary
