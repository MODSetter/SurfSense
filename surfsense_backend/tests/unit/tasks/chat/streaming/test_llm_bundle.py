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
from langchain_core.messages import AIMessage
from langchain_litellm import ChatLiteLLM
from litellm import get_optional_params

import app.agents.chat.runtime.llm_config as llm_config
import app.tasks.chat.streaming.flows.shared.llm_bundle as llm_bundle

pytestmark = pytest.mark.unit


class _CapturedChatLiteLLM:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.__class__.calls.append(kwargs)


def test_context_resolution_prefers_persisted_then_catalog_then_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        llm_config, "get_model_info", lambda _model: {"max_input_tokens": 65_536}
    )

    assert llm_config.resolve_max_input_tokens("model", 8_192) == 8_192
    assert llm_config.resolve_max_input_tokens("model") == 65_536

    monkeypatch.setattr(llm_config, "get_model_info", lambda _model: {})
    assert llm_config.resolve_max_input_tokens("model", 0) == 32_000
    assert llm_config.resolve_max_input_tokens("model", True) == 32_000


def test_litellm_preserves_ollama_num_ctx_as_provider_parameter() -> None:
    params = get_optional_params(
        model="qwen3:8b",
        custom_llm_provider="ollama_chat",
        num_ctx=8_192,
    )

    assert params["num_ctx"] == 8_192


async def test_sanitized_llm_admits_all_sync_and_async_generation_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = llm_config.SanitizedChatLiteLLM(model="openai/test", api_key="test")
    llm.profile = {
        "max_input_tokens": 4_096,
        "token_count_models": ["openai/test"],
    }
    monkeypatch.setattr(
        llm_config.SanitizedChatLiteLLM,
        "_count_context_tokens",
        lambda _self, _messages: 1,
    )
    captured: list[list[Any]] = []

    def fake_generate(_self: Any, messages: list[Any], *_args: Any, **_kwargs: Any):
        captured.append(messages)
        return "generated"

    def fake_stream(_self: Any, messages: list[Any], *_args: Any, **_kwargs: Any):
        captured.append(messages)
        yield "streamed"

    async def fake_agenerate(
        _self: Any, messages: list[Any], *_args: Any, **_kwargs: Any
    ):
        captured.append(messages)
        return "agenerated"

    async def fake_astream(
        _self: Any, messages: list[Any], *_args: Any, **_kwargs: Any
    ):
        captured.append(messages)
        yield "astreamed"

    monkeypatch.setattr(ChatLiteLLM, "_generate", fake_generate)
    monkeypatch.setattr(ChatLiteLLM, "_stream", fake_stream)
    monkeypatch.setattr(ChatLiteLLM, "_agenerate", fake_agenerate)
    monkeypatch.setattr(ChatLiteLLM, "_astream", fake_astream)
    messages = [
        AIMessage(
            content=[
                {"type": "thinking", "thinking": "private"},
                {"type": "text", "text": "answer"},
            ]
        )
    ]

    assert llm._generate(messages) == "generated"
    assert list(llm._stream(messages)) == ["streamed"]
    assert await llm._agenerate(messages) == "agenerated"
    assert [chunk async for chunk in llm._astream(messages)] == ["astreamed"]
    assert len(captured) == 4
    assert all(call[0].content == "answer" for call in captured)


@pytest.fixture(autouse=True)
def _patch_common_bundle_dependencies(monkeypatch: pytest.MonkeyPatch):
    """Keep these tests focused on the LLM constructor contract."""

    _CapturedChatLiteLLM.calls = []

    async def _fake_workspace(_session: Any, _workspace_id: int) -> SimpleNamespace:
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
        max_input_tokens=16_384,
        catalog={},
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
    assert llm.profile["max_input_tokens"] == 16_384
    assert _CapturedChatLiteLLM.calls == [
        {
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-test",
            "temperature": 0.1,
            "streaming": True,
        }
    ]


async def test_load_llm_bundle_passes_through_operator_configured_num_ctx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one number allowed to cross into an allocation request: a size an
    operator set on the connection."""
    connection = SimpleNamespace(
        provider="ollama_chat",
        api_key=None,
        base_url="http://ollama:11434",
        extra={"litellm_params": {"num_ctx": 12_288}},
    )
    model = SimpleNamespace(
        id=8,
        model_id="qwen3:8b",
        display_name="Qwen 3 8B",
        connection=connection,
        max_input_tokens=32_000,
        catalog={},
    )

    async def _fake_db_model(_session: Any, *, model_id: int, workspace: Any) -> Any:
        return model

    monkeypatch.setattr(llm_bundle, "_load_db_model", _fake_db_model)
    monkeypatch.setattr(
        llm_bundle,
        "to_litellm",
        lambda _conn, _model_id: (
            "ollama_chat/qwen3:8b",
            {"api_base": "http://ollama:11434", "num_ctx": 12_288},
        ),
    )

    llm, _, error = await llm_bundle.load_llm_bundle(
        object(), config_id=8, workspace_id=42
    )

    assert error is None
    assert llm.profile["max_input_tokens"] == 32_000
    assert _CapturedChatLiteLLM.calls[-1]["num_ctx"] == 12_288


async def test_load_llm_bundle_never_invents_an_ollama_num_ctx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The budget caps what we send; it must not become a size Ollama is asked
    to reserve. Ollama can only shrink the context to survive a load-time OOM
    while that sizing stays automatic, and an invented ``num_ctx`` removes it.
    """
    connection = SimpleNamespace(
        provider="ollama_chat",
        api_key=None,
        base_url="http://ollama:11434",
        extra={},
    )
    model = SimpleNamespace(
        id=9,
        model_id="qwen3:8b",
        display_name="Qwen 3 8B",
        connection=connection,
        max_input_tokens=24_576,
        catalog={},
    )

    async def _fake_db_model(_session: Any, *, model_id: int, workspace: Any) -> Any:
        return model

    monkeypatch.setattr(llm_bundle, "_load_db_model", _fake_db_model)
    monkeypatch.setattr(
        llm_bundle,
        "to_litellm",
        lambda _conn, _model_id: (
            "ollama_chat/qwen3:8b",
            {"api_base": "http://ollama:11434"},
        ),
    )

    llm, _, error = await llm_bundle.load_llm_bundle(
        object(), config_id=9, workspace_id=42
    )

    assert error is None
    assert llm.profile["max_input_tokens"] == 24_576
    assert "num_ctx" not in _CapturedChatLiteLLM.calls[-1]


async def test_load_llm_bundle_ignores_stale_lm_studio_loaded_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A loaded-context snapshot goes stale as soon as LM Studio reloads the
    model, so it must never clamp the configured budget."""
    connection = SimpleNamespace(
        provider="lm_studio",
        api_key=None,
        base_url="http://lm-studio:1234/v1",
        extra={},
    )
    model = SimpleNamespace(
        id=10,
        model_id="google/gemma",
        display_name="Gemma",
        connection=connection,
        max_input_tokens=262_144,
        catalog={"loaded_context_length": 8_192},
    )

    async def _fake_db_model(_session: Any, *, model_id: int, workspace: Any) -> Any:
        return model

    monkeypatch.setattr(llm_bundle, "_load_db_model", _fake_db_model)
    monkeypatch.setattr(
        llm_bundle,
        "to_litellm",
        lambda _conn, _model_id: (
            "openai/google/gemma",
            {"api_base": "http://lm-studio:1234/v1"},
        ),
    )

    llm, _, error = await llm_bundle.load_llm_bundle(
        object(), config_id=10, workspace_id=42
    )

    assert error is None
    assert llm.profile["max_input_tokens"] == 262_144
    assert "num_ctx" not in _CapturedChatLiteLLM.calls[-1]


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
