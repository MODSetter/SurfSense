"""Contracts for chat LLM construction in streaming flows.

``stream_new_chat`` / ``stream_resume_chat`` depend on LangChain receiving
token chunks from ``ChatLiteLLM``. ``langchain-litellm`` defaults
``streaming`` to ``False``, so the shared bundle loader must opt in
explicitly for both DB-backed and global model paths.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import app.tasks.chat.streaming.flows.shared.llm_bundle as llm_bundle

pytestmark = pytest.mark.unit


class _CapturedChatLiteLLM:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.__class__.calls.append(kwargs)


@pytest.fixture(autouse=True)
def _patch_common_bundle_dependencies(monkeypatch: pytest.MonkeyPatch):
    """Keep these tests focused on the LLM constructor contract."""

    _CapturedChatLiteLLM.calls = []

    async def _fake_workspace(
        _session: Any, _workspace_id: int
    ) -> SimpleNamespace:
        return SimpleNamespace(id=42, user_id="user-1")

    monkeypatch.setattr(llm_bundle, "_load_workspace", _fake_workspace)
    monkeypatch.setattr(llm_bundle, "SanitizedChatLiteLLM", _CapturedChatLiteLLM)
    monkeypatch.setattr(llm_bundle, "register_model_usage_metadata", lambda **_kw: None)
    monkeypatch.setattr(
        llm_bundle,
        "has_capability",
        lambda _model, capability: capability in {"chat", "vision"},
    )

    return None


async def test_load_llm_bundle_enables_streaming_for_db_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = SimpleNamespace(
        provider="openai",
        api_key="sk-test",
        base_url=None,
        extra={"litellm_params": {"temperature": 0.1}},
    )
    model = SimpleNamespace(
        id=7,
        model_id="gpt-4o-mini",
        display_name="GPT 4o Mini",
        connection=connection,
    )

    async def _fake_db_model(_session: Any, *, model_id: int, workspace: Any) -> Any:
        assert model_id == 7
        assert workspace.id == 42
        return model

    monkeypatch.setattr(llm_bundle, "_load_db_model", _fake_db_model)
    monkeypatch.setattr(
        llm_bundle,
        "to_litellm",
        lambda _conn, _model_id: (
            "openai/gpt-4o-mini",
            {"api_key": "sk-test", "temperature": 0.1},
        ),
    )

    llm, agent_config, error = await llm_bundle.load_llm_bundle(
        object(),
        config_id=7,
        workspace_id=42,
    )

    assert error is None
    assert llm is not None
    assert agent_config is not None
    assert _CapturedChatLiteLLM.calls == [
        {
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-test",
            "temperature": 0.1,
            "streaming": True,
        }
    ]


async def test_load_llm_bundle_enables_streaming_for_global_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global_model = {
        "id": -11,
        "connection_id": -101,
        "model_id": "claude-sonnet-4-5",
        "display_name": "Claude Sonnet",
        "billing_tier": "premium",
    }
    global_connection = {
        "id": -101,
        "provider": "anthropic",
        "api_key": "sk-ant-test",
        "base_url": None,
        "extra": {"litellm_params": {"temperature": 0.2}},
    }
    monkeypatch.setattr(
        llm_bundle.config,
        "GLOBAL_MODELS",
        [global_model],
        raising=False,
    )
    monkeypatch.setattr(
        llm_bundle.config,
        "GLOBAL_CONNECTIONS",
        [global_connection],
        raising=False,
    )
    monkeypatch.setattr(
        llm_bundle,
        "to_litellm",
        lambda _conn, _model_id: (
            "anthropic/claude-sonnet-4-5",
            {"api_key": "sk-ant-test", "temperature": 0.2},
        ),
    )

    llm, agent_config, error = await llm_bundle.load_llm_bundle(
        object(),
        config_id=-11,
        workspace_id=42,
    )

    assert error is None
    assert llm is not None
    assert agent_config is not None
    assert _CapturedChatLiteLLM.calls == [
        {
            "model": "anthropic/claude-sonnet-4-5",
            "api_key": "sk-ant-test",
            "temperature": 0.2,
            "streaming": True,
        }
    ]
