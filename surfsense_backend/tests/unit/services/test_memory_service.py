"""Unit tests for the first-class memory service."""

from types import SimpleNamespace

import pytest

from app.services.memory import (
    MemoryScope,
    reset_memory,
    save_memory,
)

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.added = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.mark.asyncio
async def test_save_memory_saves_heading_based_memory(monkeypatch) -> None:
    target = SimpleNamespace(memory_md="")
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="## Facts\n- 2026-05-19: Anish works on SurfSense\n",
        session=session,
    )

    assert result.status == "saved"
    assert target.memory_md.startswith("## Facts")
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_save_memory_accepts_legacy_marker_payload(monkeypatch) -> None:
    target = SimpleNamespace(memory_md="")
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="- (2026-05-19) [fact] Legacy marker memory\n",
        session=session,
    )

    assert result.status == "saved"
    assert target.memory_md == "## Memory\n- 2026-05-19: Legacy marker memory"


@pytest.mark.asyncio
async def test_save_memory_rejects_long_no_heading_payload(monkeypatch) -> None:
    target = SimpleNamespace(memory_md="## Facts\n- 2026-05-19: Existing\n")
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="reasoning text before NO_UPDATE should not become saved memory",
        session=session,
    )

    assert result.status == "error"
    assert session.commit_calls == 0
    assert target.memory_md.startswith("## Facts")


@pytest.mark.asyncio
async def test_save_memory_no_update_sentinel_is_no_op(monkeypatch) -> None:
    existing = "## Preferences\n- 2026-05-20: Existing preference\n"
    target = SimpleNamespace(memory_md=existing)
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="NO_UPDATE",
        session=session,
    )

    assert result.status == "no_op"
    assert result.memory_md == existing
    assert target.memory_md == existing
    assert session.commit_calls == 0


@pytest.mark.asyncio
async def test_save_memory_no_update_sentinel_is_case_insensitive(monkeypatch) -> None:
    existing = "## Preferences\n- 2026-05-20: Existing preference\n"
    target = SimpleNamespace(memory_md=existing)
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await save_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        content="  no update  ",
        session=session,
    )

    assert result.status == "no_op"
    assert result.memory_md == existing
    assert target.memory_md == existing
    assert session.commit_calls == 0


@pytest.mark.asyncio
async def test_save_memory_grandfathers_existing_team_personal_heading(
    monkeypatch,
) -> None:
    content = "## Preferences\n- 2026-05-19: Existing legacy heading\n"
    target = SimpleNamespace(shared_memory_md=content)
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
    assert result.warnings
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_reset_memory_clears_memory(monkeypatch) -> None:
    target = SimpleNamespace(memory_md="## Facts\n- 2026-05-19: Existing\n")
    session = _FakeSession()

    async def fake_load_target(**_kwargs):
        return target

    monkeypatch.setattr("app.services.memory.service._load_target", fake_load_target)

    result = await reset_memory(
        scope=MemoryScope.USER,
        target_id="00000000-0000-0000-0000-000000000000",
        session=session,
    )

    assert result.status == "saved"
    assert target.memory_md == ""
