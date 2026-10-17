import json
from pathlib import Path

import pytest

from modules.llm.subscriptions.claude.status import ClaudeState, read_status
from tests.claude_stand_in import SIGNED_IN, SIGNED_OUT, claude_stand_in

pytestmark = pytest.mark.unit


def test_no_binary_is_not_installed() -> None:
    """Nothing found is the not-installed state the dialog explains."""
    assert read_status(None).state is ClaudeState.NOT_INSTALLED


def test_a_signed_in_plan_is_ready_with_its_account(tmp_path: Path) -> None:
    """A claude.ai login is ready, with the account the dialog names."""
    status = read_status(claude_stand_in(tmp_path))

    assert status.state is ClaudeState.READY
    assert status.email == "ada@example.com"
    assert status.plan == "max"
    assert status.version == "2.1.301"


def test_not_signed_in_is_signed_out(tmp_path: Path) -> None:
    """An installed Claude Code with no login asks the user to sign in."""
    status = read_status(claude_stand_in(tmp_path, auth=SIGNED_OUT))

    assert status.state is ClaudeState.SIGNED_OUT


def test_a_console_login_is_not_a_plan(tmp_path: Path) -> None:
    """Only a claude.ai login carries a plan; a Console login bills an API account."""
    console = {**SIGNED_IN, "authMethod": "console", "subscriptionType": None}

    status = read_status(claude_stand_in(tmp_path, auth=console))

    assert status.state is ClaudeState.SIGNED_OUT


def test_an_old_claude_code_is_too_old(tmp_path: Path) -> None:
    """A version below the oldest one measured asks the user to update."""
    status = read_status(claude_stand_in(tmp_path, version="2.0.12 (Claude Code)"))

    assert status.state is ClaudeState.TOO_OLD
    assert status.version == "2.0.12"


def test_the_oldest_tested_version_is_accepted(tmp_path: Path) -> None:
    """The minimum itself is new enough."""
    status = read_status(claude_stand_in(tmp_path, version="2.1.300 (Claude Code)"))

    assert status.state is ClaudeState.READY


def test_an_unreadable_sign_in_answer_is_signed_out(tmp_path: Path) -> None:
    """A sign-in answer that is not JSON cannot show a login, so asks for one."""
    status = read_status(claude_stand_in(tmp_path, auth="Error: keychain locked"))

    assert status.state is ClaudeState.SIGNED_OUT


def test_an_unreadable_version_is_too_old(tmp_path: Path) -> None:
    """A version that cannot be read cannot be shown to be new enough."""
    status = read_status(claude_stand_in(tmp_path, version="claude: unknown"))

    assert status.state is ClaudeState.TOO_OLD


def test_a_claude_code_that_hangs_is_too_old(tmp_path: Path) -> None:
    """It never says its version, so it cannot be shown to be new enough."""
    status = read_status(claude_stand_in(tmp_path, hang_seconds=3), timeout=0.5)

    assert status.state is ClaudeState.TOO_OLD


def test_the_status_check_runs_through_surfsenses_proxy(tmp_path: Path) -> None:
    """It contacts nothing today; were a later Claude Code to, egress still holds."""
    env_log = tmp_path / "env.json"

    read_status(
        claude_stand_in(tmp_path, env_log=env_log), proxy_url="http://127.0.0.1:9"
    )

    started_with = json.loads(env_log.read_text())
    assert started_with["HTTPS_PROXY"] == "http://127.0.0.1:9"
    assert started_with["ANTHROPIC_API_KEY"] == ""
    assert started_with["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
