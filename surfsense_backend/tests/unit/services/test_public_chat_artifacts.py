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


@pytest.mark.asyncio
async def test_legacy_public_artifact_format_is_upcast_without_mutating_snapshot():
    data = {
        "artifact_ids": [5],
        "messages": [
            {
                "content": [
                    {
                        "type": "tool-call",
                        "toolName": "save_artifact",
                        "result": {"status": "saved", "artifact_id": 5},
                    }
                ]
            }
        ],
    }
    rows = MagicMock()
    rows.all.return_value = [(5, "pdf")]
    session = AsyncMock()
    session.execute.return_value = rows

    upcast = await public_chat_service._upcast_legacy_public_artifact_formats(
        session, data
    )

    assert upcast[0]["content"][0]["result"]["format"] == "pdf"
    assert "format" not in data["messages"][0]["content"][0]["result"]


@pytest.mark.asyncio
async def test_legacy_public_artifact_format_requires_snapshot_allowlist():
    messages = [
        {
            "content": [
                {
                    "type": "tool-call",
                    "toolName": "save_artifact",
                    "result": {"status": "saved", "artifact_id": 9},
                }
            ]
        }
    ]
    session = AsyncMock()

    upcast = await public_chat_service._upcast_legacy_public_artifact_formats(
        session,
        {"artifact_ids": [5], "messages": messages},
    )

    assert upcast is messages
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_public_artifact_format_skips_compatibility_query():
    messages = [
        {
            "content": [
                {
                    "type": "tool-call",
                    "toolName": "save_artifact",
                    "result": {
                        "status": "saved",
                        "artifact_id": 5,
                        "format": "pdf",
                    },
                }
            ]
        }
    ]
    session = AsyncMock()

    upcast = await public_chat_service._upcast_legacy_public_artifact_formats(
        session,
        {"artifact_ids": [5], "messages": messages},
    )

    assert upcast is messages
    session.execute.assert_not_called()


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


@pytest.mark.asyncio
async def test_podcast_snapshot_carries_artifact_id_and_no_storage_key():
    from app.podcasts.persistence import PodcastStatus

    podcast = SimpleNamespace(
        id=7,
        title="Ep",
        podcast_transcript=None,
        artifact_id=42,
        workspace_id=3,
        status=PodcastStatus.READY,
    )
    info = await public_chat_service._get_podcast_for_snapshot(
        _session_returning(podcast), 7
    )

    assert info["artifact_id"] == 42
    assert info["workspace_id"] == 3
    assert "storage_key" not in info
    assert "storage_backend" not in info
