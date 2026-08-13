"""Authenticated artifact door: artifact-ref extraction + route wiring.

Extraction is the load-bearing seam (a broken parse silently drops a user's
generated file), so it gets direct coverage; the route smoke asserts the
door is mounted and 404s an unknown workspace before any subagent run.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.artifacts.access.authenticated as door
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run import (
    _artifacts_from_messages,
    _final_text,
)
from app.auth.context import AuthContext
from app.db import get_async_session
from app.users import get_auth_context

pytestmark = pytest.mark.unit


class _ToolMessage:
    def __init__(self, content: str):
        self.content = content


class _AIMessage:
    def __init__(self, content):
        self.content = content


def _save_receipt(artifact_id: int, generation: int = 1) -> _ToolMessage:
    return _ToolMessage(
        json.dumps(
            {
                "status": "saved",
                "artifact_id": artifact_id,
                "generation": generation,
                "title": "Quarterly report",
                "files": [
                    {
                        "file_id": 99,
                        "role": "primary",
                        "filename": "report.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 4096,
                    }
                ],
            }
        )
    )


def test_extracts_saved_artifact(monkeypatch):
    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run.ToolMessage",
        _ToolMessage,
    )
    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run.AIMessage",
        _AIMessage,
    )
    messages = [
        _ToolMessage(json.dumps({"status": "ok", "note": "verified"})),  # unrelated
        _save_receipt(42),
        _AIMessage("Done — saved report.pdf."),
    ]
    artifacts = _artifacts_from_messages(messages)
    assert [a.artifact_id for a in artifacts] == [42]
    assert artifacts[0].files[0].file_id == 99
    assert artifacts[0].files[0].mime_type == "application/pdf"
    assert _final_text(messages) == "Done — saved report.pdf."


def test_latest_generation_wins(monkeypatch):
    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run.ToolMessage",
        _ToolMessage,
    )
    artifacts = _artifacts_from_messages([_save_receipt(7, 1), _save_receipt(7, 2)])
    assert len(artifacts) == 1
    assert artifacts[0].generation == 2


def test_empty_run_returns_no_artifacts(monkeypatch):
    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run.ToolMessage",
        _ToolMessage,
    )
    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run.AIMessage",
        _AIMessage,
    )
    messages = [_AIMessage("I could not build that.")]
    assert _artifacts_from_messages(messages) == []
    assert _final_text(messages) == "I could not build that."


class _FakeResult:
    def scalars(self):
        return self

    def first(self):
        return None


class _FakeSession:
    async def execute(self, *_a, **_k):
        return _FakeResult()


def test_unknown_workspace_returns_404(monkeypatch):
    monkeypatch.setattr(door, "is_sandbox_enabled", lambda: True)

    async def _allow(*_a, **_k):
        return None

    monkeypatch.setattr(door, "check_workspace_access", _allow)

    api = FastAPI()
    api.include_router(door.build_authenticated_artifact_router())

    async def _session_override():
        yield _FakeSession()

    def _auth_override():
        return AuthContext.session(SimpleNamespace(id=uuid4()))

    api.dependency_overrides[get_async_session] = _session_override
    api.dependency_overrides[get_auth_context] = _auth_override

    resp = TestClient(api).post(
        "/workspaces/9999/artifacts/generate", json={"prompt": "make a pdf"}
    )
    assert resp.status_code == 404
