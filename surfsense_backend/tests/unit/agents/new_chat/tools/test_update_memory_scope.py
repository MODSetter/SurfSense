"""Unit tests for memory scope validation."""

import pytest

from app.agents.new_chat.tools.update_memory import _save_memory, _validate_memory_scope

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


def test_validate_memory_scope_rejects_user_sections_in_team_scope() -> None:
    content = "## About the user\n- (2026-04-10) Student studying DSA\n"
    result = _validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"
    assert "personal sections" in result["message"]


def test_validate_memory_scope_rejects_team_sections_in_user_scope() -> None:
    content = "## Team decisions\n- (2026-04-10) Python-first backend policy\n"
    result = _validate_memory_scope(content, "user")
    assert result is not None
    assert result["status"] == "error"
    assert "team sections" in result["message"]


def test_validate_memory_scope_normalizes_heading_case_and_spacing() -> None:
    content = "##   About   The   User  \n- (2026-04-10) Student\n"
    result = _validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_save_memory_blocks_cross_scope_write_before_commit() -> None:
    recorder = _Recorder()
    result = await _save_memory(
        updated_memory="## About the user\n- (2026-04-10) Student\n",
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
async def test_save_memory_allows_valid_scope_and_commits() -> None:
    recorder = _Recorder()
    content = "## Team decisions\n- (2026-04-10) Python-first backend policy\n"
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
