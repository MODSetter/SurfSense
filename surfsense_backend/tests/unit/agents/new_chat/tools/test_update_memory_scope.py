"""Unit tests for memory scope validation and bullet format validation."""

import pytest

from app.agents.new_chat.tools.update_memory import (
    _save_memory,
    _validate_bullet_format,
    _validate_memory_scope,
)

pytestmark = pytest.mark.unit


class _Recorder:
    def __init__(self) -> None:
        self.applied_content: str | None = None
        self.commit_calls = 0
        self.rollback_calls = 0

    def apply(self, content: str) -> None:
        self.applied_content = content

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


# ---------------------------------------------------------------------------
# _validate_memory_scope — marker-based
# ---------------------------------------------------------------------------


def test_validate_memory_scope_rejects_pref_marker_in_team_scope() -> None:
    content = "- (2026-04-10) [pref] Prefers dark mode\n"
    result = _validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"
    assert "[pref]" in result["message"]


def test_validate_memory_scope_rejects_instr_marker_in_team_scope() -> None:
    content = "- (2026-04-10) [instr] Always respond in Spanish\n"
    result = _validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"
    assert "[instr]" in result["message"]


def test_validate_memory_scope_rejects_both_personal_markers_in_team() -> None:
    content = (
        "- (2026-04-10) [pref] Prefers dark mode\n"
        "- (2026-04-10) [instr] Always respond in Spanish\n"
    )
    result = _validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"
    assert "[instr]" in result["message"]
    assert "[pref]" in result["message"]


def test_validate_memory_scope_allows_fact_in_team_scope() -> None:
    content = "- (2026-04-10) [fact] Office is in downtown Seattle\n"
    result = _validate_memory_scope(content, "team")
    assert result is None


def test_validate_memory_scope_allows_all_markers_in_user_scope() -> None:
    content = (
        "- (2026-04-10) [fact] Python developer\n"
        "- (2026-04-10) [pref] Prefers concise answers\n"
        "- (2026-04-10) [instr] Always use bullet points\n"
    )
    result = _validate_memory_scope(content, "user")
    assert result is None


def test_validate_memory_scope_allows_any_heading_in_team() -> None:
    content = "## Architecture\n- (2026-04-10) [fact] Uses PostgreSQL for persistence\n"
    result = _validate_memory_scope(content, "team")
    assert result is None


def test_validate_memory_scope_allows_any_heading_in_user() -> None:
    content = "## My Projects\n- (2026-04-10) [fact] Working on SurfSense\n"
    result = _validate_memory_scope(content, "user")
    assert result is None


# ---------------------------------------------------------------------------
# _validate_bullet_format
# ---------------------------------------------------------------------------


def test_validate_bullet_format_passes_valid_bullets() -> None:
    content = (
        "## Work\n"
        "- (2026-04-10) [fact] Senior Python developer\n"
        "- (2026-04-10) [pref] Prefers dark mode\n"
        "- (2026-04-10) [instr] Always respond in bullet points\n"
    )
    warnings = _validate_bullet_format(content)
    assert warnings == []


def test_validate_bullet_format_warns_on_missing_marker() -> None:
    content = "- (2026-04-10) Senior Python developer\n"
    warnings = _validate_bullet_format(content)
    assert len(warnings) == 1
    assert "Malformed bullet" in warnings[0]


def test_validate_bullet_format_warns_on_missing_date() -> None:
    content = "- [fact] Senior Python developer\n"
    warnings = _validate_bullet_format(content)
    assert len(warnings) == 1
    assert "Malformed bullet" in warnings[0]


def test_validate_bullet_format_warns_on_unknown_marker() -> None:
    content = "- (2026-04-10) [context] Working on project X\n"
    warnings = _validate_bullet_format(content)
    assert len(warnings) == 1
    assert "Malformed bullet" in warnings[0]


def test_validate_bullet_format_ignores_non_bullet_lines() -> None:
    content = "## Some Heading\nSome paragraph text\n"
    warnings = _validate_bullet_format(content)
    assert warnings == []


def test_validate_bullet_format_warns_on_old_format_without_marker() -> None:
    content = "## About the user\n- (2026-04-10) Likes cats\n"
    warnings = _validate_bullet_format(content)
    assert len(warnings) == 1


# ---------------------------------------------------------------------------
# _save_memory — end-to-end with marker scope check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_memory_blocks_pref_in_team_before_commit() -> None:
    recorder = _Recorder()
    result = await _save_memory(
        updated_memory="- (2026-04-10) [pref] Prefers dark mode\n",
        old_memory=None,
        llm=None,
        apply_fn=recorder.apply,
        commit_fn=recorder.commit,
        rollback_fn=recorder.rollback,
        label="team memory",
        scope="team",
    )
    assert result["status"] == "error"
    assert recorder.commit_calls == 0
    assert recorder.applied_content is None


@pytest.mark.asyncio
async def test_save_memory_allows_fact_in_team_and_commits() -> None:
    recorder = _Recorder()
    content = "- (2026-04-10) [fact] Weekly standup on Mondays\n"
    result = await _save_memory(
        updated_memory=content,
        old_memory=None,
        llm=None,
        apply_fn=recorder.apply,
        commit_fn=recorder.commit,
        rollback_fn=recorder.rollback,
        label="team memory",
        scope="team",
    )
    assert result["status"] == "saved"
    assert recorder.commit_calls == 1
    assert recorder.applied_content == content


@pytest.mark.asyncio
async def test_save_memory_includes_format_warnings() -> None:
    recorder = _Recorder()
    content = "- (2026-04-10) Missing marker text\n"
    result = await _save_memory(
        updated_memory=content,
        old_memory=None,
        llm=None,
        apply_fn=recorder.apply,
        commit_fn=recorder.commit,
        rollback_fn=recorder.rollback,
        label="memory",
        scope="user",
    )
    assert result["status"] == "saved"
    assert "format_warnings" in result
    assert len(result["format_warnings"]) == 1
