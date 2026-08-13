"""A share token only serves the artifacts its own snapshot references."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.public_chat_service as public_chat_service

pytestmark = pytest.mark.unit


def _session_returning(file):
    scalars = MagicMock()
    scalars.first.return_value = file
    result = MagicMock()
    result.scalars.return_value = scalars
    session = AsyncMock()
    session.execute.return_value = result
    return session


@pytest.fixture
def snapshot_with_artifact_5(monkeypatch):
    async def fake_snapshot(*_args, **_kwargs):
        return SimpleNamespace(snapshot_data={"artifact_ids": [5]})

    monkeypatch.setattr(public_chat_service, "get_snapshot_by_token", fake_snapshot)


@pytest.mark.asyncio
async def test_referenced_artifact_is_served(snapshot_with_artifact_5):
    file = SimpleNamespace(storage_key="k", mime_type="image/png")
    session = _session_returning(file)

    served = await public_chat_service.get_snapshot_artifact_file(session, "tok", 5)

    assert served is file


@pytest.mark.asyncio
async def test_unreferenced_artifact_is_refused_without_a_query(
    snapshot_with_artifact_5,
):
    session = _session_returning(SimpleNamespace())

    served = await public_chat_service.get_snapshot_artifact_file(session, "tok", 9)

    assert served is None
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_snapshot_predating_the_allowlist_serves_nothing(monkeypatch):
    async def fake_snapshot(*_args, **_kwargs):
        return SimpleNamespace(snapshot_data={"messages": []})

    monkeypatch.setattr(public_chat_service, "get_snapshot_by_token", fake_snapshot)
    session = _session_returning(SimpleNamespace())

    served = await public_chat_service.get_snapshot_artifact_file(session, "tok", 5)

    assert served is None


@pytest.mark.asyncio
async def test_referenced_video_artifact_is_served(snapshot_with_artifact_5):
    artifact = SimpleNamespace(id=5, format="video")
    session = _session_returning(artifact)

    served = await public_chat_service.get_snapshot_video_artifact(session, "tok", 5)

    assert served is artifact


@pytest.mark.asyncio
async def test_unreferenced_video_artifact_is_refused_without_a_query(
    snapshot_with_artifact_5,
):
    session = _session_returning(SimpleNamespace())

    served = await public_chat_service.get_snapshot_video_artifact(session, "tok", 9)

    assert served is None
    session.execute.assert_not_called()
