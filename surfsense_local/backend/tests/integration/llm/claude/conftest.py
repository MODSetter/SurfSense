import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from modules.llm.subscriptions.claude import locate, plan_generator
from modules.llm.subscriptions.claude import models as claude_models
from modules.llm.subscriptions.claude import proxy as claude_proxy
from tests.claude_run_stand_in import ScriptedRun, answer
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
    if sys.platform == "win32":
        # The stand-in is a batch file, which Windows runs as a process does; only
        # the Agent SDK refuses one, and no test here starts it.
        monkeypatch.setattr(locate, "WINDOWS_NAME", "claude.cmd")

    def install(*, installed: bool = True, **stand_in: object) -> Path | None:
        return claude_stand_in(bin_dir, **stand_in) if installed else None

    return install


class FakeClaude:
    """Every Claude Code run the API opens, scripted.

    `runs` are handed out in order; past them, a run answers a title request
    with a title and anything else with the next of `replies`, so a chat and
    the title generated beside it never take each other's answer.
    """

    def __init__(self) -> None:
        self.runs: list[ScriptedRun] = []
        self.replies: list[list] = []
        self.opened: list[ScriptedRun] = []

    def _respond(self, prompt: object) -> list:
        text = prompt if isinstance(prompt, str) else prompt[-1]["text"]
        if text.startswith("Write a 2-5 word"):
            return answer("A title")
        reply = self.replies.pop(0)
        # A reply can act when it is sent, as something changing mid-run.
        return reply() if callable(reply) else reply

    async def open(self, options: object) -> ScriptedRun:
        run = self.runs.pop(0) if self.runs else ScriptedRun(respond=self._respond)
        run.options = options
        self.opened.append(run)
        return run


@pytest.fixture
def fake_claude(monkeypatch: pytest.MonkeyPatch) -> FakeClaude:
    """Stand in for every Claude Code run, model lists and chat alike."""
    fake = FakeClaude()
    monkeypatch.setattr(claude_models, "open_run", fake.open)
    monkeypatch.setattr(plan_generator, "open_run", fake.open)
    # The API's one pool of warm chat runs, fresh for each test.
    monkeypatch.setattr(plan_generator, "_runs", None)
    # A serving API's proxy address; scripted runs never connect to it.
    monkeypatch.setattr(claude_proxy, "_url", "http://127.0.0.1:9")
    return fake
