"""Unit tests for heading-based memory validation."""

import pytest

from app.services.memory import MemoryScope, save_memory
from app.services.memory.validation import (
    validate_bullet_format,
    validate_memory_scope,
)

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def test_validate_memory_scope_rejects_new_personal_heading_in_team() -> None:
    content = "## Preferences\n- 2026-04-10: Prefers dark mode\n"
    result, _warnings = validate_memory_scope(content, "team")
    assert result is not None
    assert result["status"] == "error"
    assert "preferences" in result["message"]


def test_validate_memory_scope_allows_old_marker_payload_in_team_scope() -> None:
    content = "- (2026-04-10) [pref] Legacy personal marker remains readable\n"
    result, _warnings = validate_memory_scope(content, "team")
    assert result is None


def test_validate_memory_scope_allows_team_headings() -> None:
    content = "## Engineering Conventions\n- 2026-04-10: Uses PostgreSQL\n"
    result, _warnings = validate_memory_scope(content, "team")
    assert result is None


def test_validate_bullet_format_accepts_new_and_legacy_bullets() -> None:
    content = (
        "## Facts\n"
        "- 2026-04-10: Senior Python developer\n"
        "- (2026-04-10) [fact] Legacy fact is preserved\n"
    )
    warnings = validate_bullet_format(content)
    assert warnings == []


def test_validate_bullet_format_warns_on_nonstandard_bullet() -> None:
    content = "## Facts\n- Senior Python developer\n"
    warnings = validate_bullet_format(content)
    assert len(warnings) == 1
    assert "Non-standard memory bullet" in warnings[0]


@pytest.mark.asyncio
async def test_save_memory_blocks_new_personal_heading_in_team_before_commit(
    monkeypatch,
) -> None:
    target = type("Target", (), {"shared_memory_md": ""})()
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.TEAM,
        target_id=1,
        content="## Preferences\n- 2026-04-10: Prefers dark mode\n",
        session=session,
    )
    assert result.status == "error"
    assert session.commit_calls == 0
    assert target.shared_memory_md == ""


@pytest.mark.asyncio
async def test_save_memory_allows_grandfathered_personal_heading_in_team(
    monkeypatch,
) -> None:
    content = "## Preferences\n- 2026-04-10: Prefers dark mode\n"
    target = type("Target", (), {"shared_memory_md": content})()
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.TEAM,
        target_id=1,
        content=content,
        session=session,
    )
    assert result.status == "saved"
    assert session.commit_calls == 1
    assert target.shared_memory_md == content.strip()
    assert result.warnings


@pytest.mark.asyncio
async def test_save_memory_strips_preamble_before_heading(monkeypatch) -> None:
    target = type("Target", (), {"memory_md": ""})()
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="Sure, here is the update:\n\n## Facts\n- 2026-04-10: Likes cats\n",
        session=session,
    )
    assert result.status == "saved"
    assert target.memory_md == "## Facts\n- 2026-04-10: Likes cats"


@pytest.mark.asyncio
async def test_save_memory_rejects_long_no_heading_payload(monkeypatch) -> None:
    target = type("Target", (), {"memory_md": ""})()
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="NO_UPDATE because there is nothing durable to remember.",
        session=session,
    )
    assert result.status == "error"
    assert "## heading" in result.message
    assert session.commit_calls == 0
