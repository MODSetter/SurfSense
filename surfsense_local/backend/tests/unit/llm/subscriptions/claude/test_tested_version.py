import logging
from pathlib import Path

import pytest

from modules.llm.subscriptions.claude.tested_version import note_untested
from tests.claude_stand_in import claude_stand_in

pytestmark = pytest.mark.unit


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_a_claude_code_newer_than_any_tested_is_named_in_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An update may break what SurfSense measured; the log says where to look."""
    binary = claude_stand_in(tmp_path, version="2.2.0 (Claude Code)")

    note_untested(binary)

    (warning,) = _warnings(caplog)
    assert "2.2.0" in warning
    assert "2.1.301" in warning


def test_a_tested_claude_code_is_not_named(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The version the docs were measured on needs no warning."""
    note_untested(claude_stand_in(tmp_path, version="2.1.301 (Claude Code)"))

    assert _warnings(caplog) == []


def test_each_untested_binary_is_named_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Every run checks; the log does not repeat itself for each one."""
    binary = claude_stand_in(tmp_path, version="2.3.1 (Claude Code)")

    note_untested(binary)
    note_untested(binary)

    assert len(_warnings(caplog)) == 1
