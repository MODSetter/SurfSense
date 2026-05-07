"""Behavior tests for streaming runtime helpers."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from app.tasks.chat.streaming import runtime

pytestmark = pytest.mark.unit


async def test_preflight_llm_calls_litellm_when_model_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    async def _fake_acompletion(**kwargs: Any):
        calls.update(kwargs)
        return {"ok": True}

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        types.SimpleNamespace(acompletion=_fake_acompletion),
    )

    llm = types.SimpleNamespace(model="openai/test", api_key="k", api_base="b")
    await runtime.preflight_llm(llm, is_provider_rate_limited=lambda _: False)

    assert calls["model"] == "openai/test"
    assert calls["max_tokens"] == 1
    assert calls["timeout"] == 2.5
    assert calls["stream"] is False


async def test_preflight_llm_rethrows_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RateLimitedError(Exception):
        pass

    async def _fake_acompletion(**kwargs: Any):
        del kwargs
        raise _RateLimitedError("rl")

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        types.SimpleNamespace(acompletion=_fake_acompletion),
    )

    with pytest.raises(_RateLimitedError):
        await runtime.preflight_llm(
            types.SimpleNamespace(model="openai/test"),
            is_provider_rate_limited=lambda exc: isinstance(exc, _RateLimitedError),
        )


async def test_preflight_llm_skips_probe_for_auto_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"count": 0}

    async def _fake_acompletion(**kwargs: Any):
        del kwargs
        called["count"] += 1
        return {"ok": True}

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        types.SimpleNamespace(acompletion=_fake_acompletion),
    )

    await runtime.preflight_llm(
        types.SimpleNamespace(model="auto"),
        is_provider_rate_limited=lambda _: False,
    )
    assert called["count"] == 0


async def test_build_main_agent_for_thread_forwards_arguments() -> None:
    seen: dict[str, Any] = {}

    async def _factory(**kwargs: Any):
        seen.update(kwargs)
        return "agent"

    out = await runtime.build_main_agent_for_thread(
        _factory,
        llm="llm",
        search_space_id=1,
        db_session="db",
        connector_service="connector",
        checkpointer="cp",
        user_id="u",
        thread_id=10,
        agent_config="cfg",
        firecrawl_api_key="key",
        thread_visibility="vis",
        filesystem_selection="fs",
        disabled_tools=["a"],
        mentioned_document_ids=[5],
    )
    assert out == "agent"
    assert seen["thread_id"] == 10
    assert seen["mentioned_document_ids"] == [5]


async def test_settle_speculative_agent_build_swallows_exceptions() -> None:
    async def _boom() -> None:
        raise RuntimeError("ignore")

    import asyncio

    task = asyncio.create_task(_boom())
    await runtime.settle_speculative_agent_build(task)
    assert task.done()
