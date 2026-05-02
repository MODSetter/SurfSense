"""Cost-based premium quota unit tests.

Covers the USD-micro behaviour added in migration 140:

* ``TurnTokenAccumulator.total_cost_micros`` sums ``cost_micros`` across all
  calls in a turn — used as the debit amount when ``agent_config.is_premium``
  is true, regardless of which underlying model produced each call. This
  preserves the prior "premium turn → all calls in turn count" rule from the
  token-based system.
* ``estimate_call_reserve_micros`` scales linearly with model pricing,
  clamps to a sane floor when pricing is unknown, and respects the
  ``QUOTA_MAX_RESERVE_MICROS`` ceiling so a misconfigured "$1000/M" entry
  can't lock the whole balance on one call.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# TurnTokenAccumulator — premium-turn debit semantics
# ---------------------------------------------------------------------------


def test_total_cost_micros_sums_premium_and_free_calls():
    """A premium turn that also called a free sub-agent debits the union.

    The plan deliberately preserved the existing "premium turn → all calls
    count" behaviour because per-call premium filtering relied on
    ``LLMRouterService._premium_model_strings`` which only covers router-pool
    deployments. ``total_cost_micros`` therefore must include free-model
    calls (whose ``cost_micros`` is typically ``0``) as well as the premium
    call's actual provider cost.
    """
    from app.services.token_tracking_service import TurnTokenAccumulator

    acc = TurnTokenAccumulator()
    # Premium model (e.g. claude-opus): non-zero cost.
    acc.add(
        model="anthropic/claude-3-5-sonnet",
        prompt_tokens=1200,
        completion_tokens=400,
        total_tokens=1600,
        cost_micros=12_345,
    )
    # Free sub-agent (e.g. title-gen on a free model): zero cost.
    acc.add(
        model="gpt-4o-mini",
        prompt_tokens=120,
        completion_tokens=20,
        total_tokens=140,
        cost_micros=0,
    )
    # A second premium-priced call within the same turn.
    acc.add(
        model="anthropic/claude-3-5-sonnet",
        prompt_tokens=800,
        completion_tokens=200,
        total_tokens=1000,
        cost_micros=7_500,
    )

    assert acc.total_cost_micros == 12_345 + 0 + 7_500
    # Token totals stay correct so the FE display path still works.
    assert acc.grand_total == 1600 + 140 + 1000


def test_total_cost_micros_zero_when_no_calls():
    """An empty accumulator must report zero cost (no division-by-zero, no None)."""
    from app.services.token_tracking_service import TurnTokenAccumulator

    acc = TurnTokenAccumulator()
    assert acc.total_cost_micros == 0
    assert acc.grand_total == 0


def test_per_message_summary_groups_cost_by_model():
    """``per_message_summary`` must accumulate ``cost_micros`` per model so the
    SSE ``model_breakdown`` payload reports actual USD spend per provider.
    """
    from app.services.token_tracking_service import TurnTokenAccumulator

    acc = TurnTokenAccumulator()
    acc.add(
        model="claude-3-5-sonnet",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_micros=4_000,
    )
    acc.add(
        model="claude-3-5-sonnet",
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
        cost_micros=8_000,
    )
    acc.add(
        model="gpt-4o-mini",
        prompt_tokens=50,
        completion_tokens=10,
        total_tokens=60,
        cost_micros=200,
    )

    summary = acc.per_message_summary()
    assert summary["claude-3-5-sonnet"]["cost_micros"] == 12_000
    assert summary["claude-3-5-sonnet"]["total_tokens"] == 450
    assert summary["gpt-4o-mini"]["cost_micros"] == 200


def test_serialized_calls_includes_cost_micros():
    """``serialized_calls`` is what flows into the SSE ``call_details``
    payload; cost_micros must be present on each entry so the FE message-info
    dropdown can render per-call USD.
    """
    from app.services.token_tracking_service import TurnTokenAccumulator

    acc = TurnTokenAccumulator()
    acc.add(
        model="m",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        cost_micros=42,
    )
    serialized = acc.serialized_calls()
    assert serialized == [
        {
            "model": "m",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
            "cost_micros": 42,
            "call_kind": "chat",
        }
    ]


# ---------------------------------------------------------------------------
# estimate_call_reserve_micros — sizing and clamping
# ---------------------------------------------------------------------------


def test_reserve_returns_floor_when_model_unknown(monkeypatch):
    """If LiteLLM doesn't know the model, ``get_model_info`` raises and the
    helper falls back to the 100-micro floor — small enough that a user with
    $0.0001 left can still send a tiny request, but non-zero so we still gate
    against an empty balance.
    """
    import litellm

    from app.services import token_quota_service

    def _raise(_name):
        raise KeyError("unknown")

    monkeypatch.setattr(litellm, "get_model_info", _raise, raising=False)

    micros = token_quota_service.estimate_call_reserve_micros(
        base_model="nonexistent-model",
        quota_reserve_tokens=4000,
    )
    assert micros == token_quota_service._QUOTA_MIN_RESERVE_MICROS
    assert micros == 100


def test_reserve_returns_floor_when_pricing_is_zero(monkeypatch):
    """LiteLLM may *return* a model with both cost-per-token fields at 0
    (pricing not yet registered). The helper must not multiply 0 x tokens
    and end up reserving 0 — it must clamp to the floor.
    """
    import litellm

    from app.services import token_quota_service

    monkeypatch.setattr(
        litellm,
        "get_model_info",
        lambda _name: {"input_cost_per_token": 0, "output_cost_per_token": 0},
        raising=False,
    )

    micros = token_quota_service.estimate_call_reserve_micros(
        base_model="some-pending-model",
        quota_reserve_tokens=4000,
    )
    assert micros == token_quota_service._QUOTA_MIN_RESERVE_MICROS


def test_reserve_scales_with_model_cost(monkeypatch):
    """Claude-Opus-priced model with 4000 reserve_tokens reserves
    ~$0.36 = 360_000 micros. Critically this must NOT be clamped down to
    some small artificial cap — that was the bug the plan called out.
    """
    import litellm

    from app.config import config
    from app.services import token_quota_service

    monkeypatch.setattr(
        litellm,
        "get_model_info",
        lambda _name: {
            "input_cost_per_token": 15e-6,
            "output_cost_per_token": 75e-6,
        },
        raising=False,
    )
    monkeypatch.setattr(config, "QUOTA_MAX_RESERVE_MICROS", 1_000_000, raising=False)

    micros = token_quota_service.estimate_call_reserve_micros(
        base_model="claude-3-opus",
        quota_reserve_tokens=4000,
    )
    # 4000 * (15e-6 + 75e-6) = 4000 * 90e-6 = 0.36 USD = 360_000 micros.
    assert micros == 360_000


def test_reserve_clamps_to_max_ceiling(monkeypatch):
    """A misconfigured "$1000 / M" model with 4000 reserve_tokens would
    nominally compute to $4 = 4_000_000 micros. The ceiling
    ``QUOTA_MAX_RESERVE_MICROS`` must clamp that so a bad pricing entry
    can't lock the user's whole balance on one call.
    """
    import litellm

    from app.config import config
    from app.services import token_quota_service

    monkeypatch.setattr(
        litellm,
        "get_model_info",
        lambda _name: {
            "input_cost_per_token": 1e-3,
            "output_cost_per_token": 0,
        },
        raising=False,
    )
    monkeypatch.setattr(config, "QUOTA_MAX_RESERVE_MICROS", 1_000_000, raising=False)

    micros = token_quota_service.estimate_call_reserve_micros(
        base_model="oops-misconfigured",
        quota_reserve_tokens=4000,
    )
    assert micros == 1_000_000


def test_reserve_uses_default_when_quota_reserve_tokens_missing(monkeypatch):
    """Per-config ``quota_reserve_tokens`` is optional; when ``None`` or
    zero, the helper must fall back to the global ``QUOTA_MAX_RESERVE_PER_CALL``
    so anonymous-style configs still reserve the operator-tunable default.
    """
    import litellm

    from app.config import config
    from app.services import token_quota_service

    monkeypatch.setattr(
        litellm,
        "get_model_info",
        lambda _name: {
            "input_cost_per_token": 1e-6,
            "output_cost_per_token": 1e-6,
        },
        raising=False,
    )
    monkeypatch.setattr(config, "QUOTA_MAX_RESERVE_PER_CALL", 2000, raising=False)
    monkeypatch.setattr(config, "QUOTA_MAX_RESERVE_MICROS", 1_000_000, raising=False)

    # 2000 * (1e-6 + 1e-6) = 4e-3 USD = 4000 micros
    assert (
        token_quota_service.estimate_call_reserve_micros(
            base_model="cheap", quota_reserve_tokens=None
        )
        == 4000
    )
    assert (
        token_quota_service.estimate_call_reserve_micros(
            base_model="cheap", quota_reserve_tokens=0
        )
        == 4000
    )


# ---------------------------------------------------------------------------
# TokenTrackingCallback — image vs chat usage shape
# ---------------------------------------------------------------------------


class _FakeImageUsage:
    """Mimics LiteLLM's ``ImageUsage`` (input_tokens / output_tokens shape)."""

    def __init__(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int | None = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        if total_tokens is not None:
            self.total_tokens = total_tokens


class _FakeImageResponse:
    """Mimics LiteLLM's ``ImageResponse`` — same name so the callback's
    ``type(...).__name__`` probe routes to the image branch.
    """

    def __init__(self, usage: _FakeImageUsage, response_cost: float | None = None):
        self.usage = usage
        if response_cost is not None:
            self._hidden_params = {"response_cost": response_cost}


# Re-tag the helper class as ``ImageResponse`` for the type-name probe in
# the callback. We can't simply name the class ``ImageResponse`` because
# the test runner sometimes imports test modules in surprising ways and
# we want to be explicit.
_FakeImageResponse.__name__ = "ImageResponse"


class _FakeChatUsage:
    def __init__(self, prompt: int, completion: int):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = prompt + completion


class _FakeChatResponse:
    def __init__(self, usage: _FakeChatUsage):
        self.usage = usage


@pytest.mark.asyncio
async def test_callback_reads_image_usage_input_output_tokens():
    """``TokenTrackingCallback`` must read ``input_tokens``/``output_tokens``
    for ``ImageResponse`` (LiteLLM's ImageUsage shape), NOT
    prompt_tokens/completion_tokens which is the chat shape.
    """
    from app.services.token_tracking_service import (
        TokenTrackingCallback,
        scoped_turn,
    )

    cb = TokenTrackingCallback()
    response = _FakeImageResponse(
        usage=_FakeImageUsage(input_tokens=42, output_tokens=8, total_tokens=50),
        response_cost=0.04,  # $0.04 per image
    )

    async with scoped_turn() as acc:
        await cb.async_log_success_event(
            kwargs={"model": "openai/gpt-image-1", "response_cost": 0.04},
            response_obj=response,
            start_time=None,
            end_time=None,
        )
        assert len(acc.calls) == 1
        call = acc.calls[0]
        assert call.prompt_tokens == 42
        assert call.completion_tokens == 8
        assert call.total_tokens == 50
        # 0.04 USD = 40_000 micros
        assert call.cost_micros == 40_000
        assert call.call_kind == "image_generation"


@pytest.mark.asyncio
async def test_callback_chat_path_unchanged():
    """Chat responses must still read prompt_tokens/completion_tokens."""
    from app.services.token_tracking_service import (
        TokenTrackingCallback,
        scoped_turn,
    )

    cb = TokenTrackingCallback()
    response = _FakeChatResponse(_FakeChatUsage(prompt=120, completion=30))

    async with scoped_turn() as acc:
        await cb.async_log_success_event(
            kwargs={
                "model": "openrouter/anthropic/claude-3-5-sonnet",
                "response_cost": 0.0036,
            },
            response_obj=response,
            start_time=None,
            end_time=None,
        )
        assert len(acc.calls) == 1
        call = acc.calls[0]
        assert call.prompt_tokens == 120
        assert call.completion_tokens == 30
        assert call.total_tokens == 150
        assert call.cost_micros == 3_600
        assert call.call_kind == "chat"


@pytest.mark.asyncio
async def test_callback_image_missing_response_cost_falls_back_to_zero(monkeypatch):
    """When OpenRouter omits ``usage.cost`` LiteLLM's
    ``default_image_cost_calculator`` raises. The defensive image branch in
    ``_extract_cost_usd`` must NOT call ``cost_per_token`` (which is
    chat-shaped and would raise too) — it returns 0 with a WARNING log.
    """
    import litellm

    from app.services.token_tracking_service import (
        TokenTrackingCallback,
        scoped_turn,
    )

    # Force completion_cost to raise the same way OpenRouter image-gen fails.
    def _boom(*_args, **_kwargs):
        raise ValueError("model_cost: missing entry for openrouter image model")

    monkeypatch.setattr(litellm, "completion_cost", _boom, raising=False)

    # And make sure cost_per_token is NEVER called for the image path —
    # if it were, our ``is_image=True`` branch is broken.
    cost_per_token_calls: list = []

    def _record_cost_per_token(**kwargs):
        cost_per_token_calls.append(kwargs)
        return (0.0, 0.0)

    monkeypatch.setattr(
        litellm, "cost_per_token", _record_cost_per_token, raising=False
    )

    cb = TokenTrackingCallback()
    response = _FakeImageResponse(
        usage=_FakeImageUsage(input_tokens=7, output_tokens=0)
    )

    async with scoped_turn() as acc:
        await cb.async_log_success_event(
            kwargs={"model": "openrouter/google/gemini-2.5-flash-image"},
            response_obj=response,
            start_time=None,
            end_time=None,
        )

    assert len(acc.calls) == 1
    assert acc.calls[0].cost_micros == 0
    assert acc.calls[0].call_kind == "image_generation"
    # The image branch must short-circuit before cost_per_token.
    assert cost_per_token_calls == []


# ---------------------------------------------------------------------------
# scoped_turn — ContextVar reset semantics (issue B)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scoped_turn_restores_outer_accumulator():
    """``scoped_turn`` must restore the previous ContextVar value on exit
    so a per-call wrapper inside an outer chat turn doesn't leak its
    accumulator outward (which would cause double-debit at chat-turn exit).
    """
    from app.services.token_tracking_service import (
        get_current_accumulator,
        scoped_turn,
        start_turn,
    )

    outer = start_turn()
    assert get_current_accumulator() is outer

    async with scoped_turn() as inner:
        assert get_current_accumulator() is inner
        assert inner is not outer
        inner.add(
            model="x",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost_micros=5,
        )

    # After exit the outer accumulator is restored unchanged.
    assert get_current_accumulator() is outer
    assert outer.total_cost_micros == 0
    assert len(outer.calls) == 0
    # The inner accumulator captured the call but didn't bleed into outer.
    assert inner.total_cost_micros == 5


@pytest.mark.asyncio
async def test_scoped_turn_resets_to_none_when_no_outer():
    """Running ``scoped_turn`` outside any chat turn (e.g. a background
    indexing job) must leave the ContextVar at ``None`` on exit so the
    next *unrelated* request starts clean.
    """
    from app.services.token_tracking_service import (
        _turn_accumulator,
        get_current_accumulator,
        scoped_turn,
    )

    # ContextVar default is None for a fresh test isolated context. We
    # simulate "no outer" explicitly to be robust against test order.
    token = _turn_accumulator.set(None)
    try:
        assert get_current_accumulator() is None
        async with scoped_turn() as acc:
            assert get_current_accumulator() is acc
        assert get_current_accumulator() is None
    finally:
        _turn_accumulator.reset(token)
