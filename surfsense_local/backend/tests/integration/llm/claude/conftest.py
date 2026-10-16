from collections.abc import Callable
from pathlib import Path

import pytest

from modules.llm.subscriptions.claude import models as claude_models
from tests.claude_run_stand_in import ScriptedRun
from tests.claude_stand_in import claude_stand_in

ClaudeOnThisMachine = Callable[..., Path | None]


@pytest.fixture
def claude_on_this_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ClaudeOnThisMachine:
    """Put a stand-in Claude Code where the API looks, and nothing else.

    HOME is a fresh folder, so the developer's own Claude Code is never found.
    Called with no arguments it installs a signed-in one; `installed=False`
    leaves the machine without any.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))

    def install(*, installed: bool = True, **stand_in: object) -> Path | None:
        return claude_stand_in(bin_dir, **stand_in) if installed else None

    return install


@pytest.fixture
def claude_runs(monkeypatch: pytest.MonkeyPatch) -> list[ScriptedRun]:
    """Every run the API opens, scripted; append before the request makes one."""
    runs: list[ScriptedRun] = []

    async def open_scripted(options: object) -> ScriptedRun:
        run = runs.pop(0) if runs else ScriptedRun()
        run.options = options
        return run

    monkeypatch.setattr(claude_models, "open_run", open_scripted)
    return runs
