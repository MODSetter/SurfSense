"""SurfSense ships no Claude Code (ADR 0057), and installs none either.

The Agent SDK's wheels carry Claude Code in `claude_agent_sdk/_bundled`, 241 MB;
its source package does not. `no-binary-package` in pyproject.toml makes uv build
the SDK from source, so no venv, CI cache or frozen app holds that copy. Run on
every system in CI, this fails the day that line is lost.
"""

from pathlib import Path

import claude_agent_sdk
import pytest

pytestmark = pytest.mark.unit


def test_the_installed_agent_sdk_carries_no_claude_code() -> None:
    """Every run uses the user's own Claude Code, so the SDK needs none of its own."""
    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled"

    shipped = [path.name for path in bundled.iterdir() if path.name != ".gitignore"]

    assert shipped == [], f"the Agent SDK was installed from a wheel: {shipped}"
