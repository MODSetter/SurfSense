"""Unit tests for ``QuotaCheckedVisionLLM``.

Validates that:

* Calling ``ainvoke`` routes through ``billable_call`` (premium credit
  enforcement) and forwards the inner LLM's response on success.
* The wrapper proxies non-overridden attributes to the inner LLM
  (``__getattr__``) so ``invoke`` / ``astream`` / ``with_structured_output``
  still work without quota gating (they're not used in indexing today).
* When ``billable_call`` raises ``QuotaInsufficientError`` the wrapper
  bubbles it up — the ETL pipeline catches that and falls back to OCR.
"""

from __future__ import annotations

import contextlib
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class _FakeInnerLLM:
    """Stand-in for ``langchain_litellm.ChatLiteLLM``."""

    def __init__(self, response: Any = "OCR'd content") -> None:
        self._response = response
        self.ainvoke_calls: list[Any] = []

    async def ainvoke(self, input: Any, *args: Any, **kwargs: Any) -> Any:
        self.ainvoke_calls.append(input)
        return self._response

    def some_other_method(self, x: int) -> int:
        return x * 2


@contextlib.asynccontextmanager
async def _passthrough_billable_call(**_kwargs):
    """Stand-in for billable_call that always allows the call to run."""

    class _Acc:
        total_cost_micros = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        grand_total = 0
        calls: list[Any] = []

        def per_message_summary(self) -> dict[str, dict[str, int]]:
            return {}

    yield _Acc()


@pytest.mark.asyncio
async def test_ainvoke_routes_through_billable_call(monkeypatch):
    from app.services.quota_checked_vision_llm import QuotaCheckedVisionLLM

    captured_kwargs: list[dict[str, Any]] = []

    @contextlib.asynccontextmanager
    async def _spy_billable_call(**kwargs):
        captured_kwargs.append(kwargs)
        async with _passthrough_billable_call() as acc:
            yield acc

    monkeypatch.setattr(
        "app.services.quota_checked_vision_llm.billable_call",
        _spy_billable_call,
        raising=False,
    )

    inner = _FakeInnerLLM(response="A red apple on a white table")
    user_id = uuid4()
    wrapper = QuotaCheckedVisionLLM(
        inner,
        user_id=user_id,
        search_space_id=99,
        billing_tier="premium",
        base_model="openai/gpt-4o",
        quota_reserve_tokens=4000,
    )

    result = await wrapper.ainvoke([{"text": "what is this?"}])
    assert result == "A red apple on a white table"
    assert len(inner.ainvoke_calls) == 1
    assert len(captured_kwargs) == 1
    bc_kwargs = captured_kwargs[0]
    assert bc_kwargs["user_id"] == user_id
    assert bc_kwargs["search_space_id"] == 99
    assert bc_kwargs["billing_tier"] == "premium"
    assert bc_kwargs["base_model"] == "openai/gpt-4o"
    assert bc_kwargs["quota_reserve_tokens"] == 4000
    assert bc_kwargs["usage_type"] == "vision_extraction"


@pytest.mark.asyncio
async def test_ainvoke_propagates_quota_insufficient_error(monkeypatch):
    from app.services.billable_calls import QuotaInsufficientError
    from app.services.quota_checked_vision_llm import QuotaCheckedVisionLLM

    @contextlib.asynccontextmanager
    async def _denying_billable_call(**_kwargs):
        raise QuotaInsufficientError(
            usage_type="vision_extraction",
            used_micros=5_000_000,
            limit_micros=5_000_000,
            remaining_micros=0,
        )
        yield  # unreachable but required for asynccontextmanager type

    monkeypatch.setattr(
        "app.services.quota_checked_vision_llm.billable_call",
        _denying_billable_call,
        raising=False,
    )

    inner = _FakeInnerLLM()
    wrapper = QuotaCheckedVisionLLM(
        inner,
        user_id=uuid4(),
        search_space_id=1,
        billing_tier="premium",
        base_model="openai/gpt-4o",
        quota_reserve_tokens=4000,
    )

    with pytest.raises(QuotaInsufficientError):
        await wrapper.ainvoke([{"text": "x"}])

    # Inner LLM never ran on a denied reservation.
    assert inner.ainvoke_calls == []


@pytest.mark.asyncio
async def test_proxies_non_overridden_attributes_to_inner():
    """``__getattr__`` forwards anything not on the proxy itself, so any
    method we didn't explicitly override (``invoke``, ``astream``,
    ``with_structured_output``, etc.) still works — just without quota
    gating, which is fine because the indexer only ever calls ainvoke.
    """
    from app.services.quota_checked_vision_llm import QuotaCheckedVisionLLM

    inner = _FakeInnerLLM()
    wrapper = QuotaCheckedVisionLLM(
        inner,
        user_id=uuid4(),
        search_space_id=1,
        billing_tier="premium",
        base_model="openai/gpt-4o",
        quota_reserve_tokens=4000,
    )

    # ``some_other_method`` is on the inner only.
    assert wrapper.some_other_method(7) == 14
