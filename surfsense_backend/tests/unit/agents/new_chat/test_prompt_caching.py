"""Tests for ``apply_litellm_prompt_caching`` in
:mod:`app.agents.new_chat.prompt_caching`.

The helper replaces the legacy ``AnthropicPromptCachingMiddleware`` (which
never activated for our LiteLLM stack) with LiteLLM-native multi-provider
prompt caching. It mutates ``llm.model_kwargs`` so the kwargs flow to
``litellm.completion(...)``. The tests below pin its public contract:

1. Always sets BOTH ``role: system`` and ``index: -1`` injection points so
   savings compound across multi-turn conversations on Anthropic-family
   providers.
2. Adds ``prompt_cache_key``/``prompt_cache_retention`` only for
   single-model OPENAI/DEEPSEEK/XAI configs (where OpenAI's automatic
   prompt-cache surface is available).
3. Treats ``ChatLiteLLMRouter`` (auto-mode) as universal-only — no
   OpenAI-only kwargs because the router fans out across providers.
4. Idempotent: user-supplied values in ``model_kwargs`` are preserved.
5. Defensive: LLMs without a writable ``model_kwargs`` are silently
   skipped rather than raising.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.prompt_caching import apply_litellm_prompt_caching

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeLLM:
    """Stand-in for ``ChatLiteLLM``/``SanitizedChatLiteLLM``.

    The helper only inspects ``getattr(llm, "model_kwargs", None)``,
    ``getattr(llm, "model", None)``, and ``type(llm).__name__``. A simple
    object suffices — we don't need to spin up real LangChain/LiteLLM
    machinery for unit tests of the helper's logic.
    """

    def __init__(
        self,
        model: str = "openai/gpt-4o",
        model_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.model_kwargs: dict[str, Any] = dict(model_kwargs) if model_kwargs else {}


class ChatLiteLLMRouter:
    """Class-name-only impostor of the real router.

    The helper's router gate is ``type(llm).__name__ == "ChatLiteLLMRouter"``
    (a deliberate stringly-typed check to avoid an import cycle with
    ``app.services.llm_router_service``). Reusing the same class name here
    triggers the same code path without instantiating a real ``Router``.
    """

    def __init__(self) -> None:
        self.model = "auto"
        self.model_kwargs: dict[str, Any] = {}


def _make_cfg(**overrides: Any) -> AgentConfig:
    """Build an ``AgentConfig`` with sensible defaults for the helper test."""
    defaults: dict[str, Any] = {
        "provider": "OPENAI",
        "model_name": "gpt-4o",
        "api_key": "k",
    }
    return AgentConfig(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# (a) Universal injection points
# ---------------------------------------------------------------------------


def test_sets_both_cache_control_injection_points_with_no_config() -> None:
    """Bare call (no agent_config, no thread_id) still sets the two
    universal breakpoints — these cost nothing on providers that don't
    consume them and unlock caching on every supported provider."""
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm)

    points = llm.model_kwargs["cache_control_injection_points"]
    assert {"location": "message", "role": "system"} in points
    assert {"location": "message", "index": -1} in points
    assert len(points) == 2


def test_injection_points_set_for_anthropic_config() -> None:
    """Anthropic-family configs need the marker — verify it lands."""
    cfg = _make_cfg(provider="ANTHROPIC", model_name="claude-3-5-sonnet")
    llm = _FakeLLM(model="anthropic/claude-3-5-sonnet")

    apply_litellm_prompt_caching(llm, agent_config=cfg)

    assert "cache_control_injection_points" in llm.model_kwargs


# ---------------------------------------------------------------------------
# (b) Idempotency / user override wins
# ---------------------------------------------------------------------------


def test_does_not_overwrite_user_supplied_cache_control_injection_points() -> None:
    """Users who set their own injection points (e.g. with ``ttl: "1h"``
    via ``litellm_params``) keep them — the helper merges, never
    clobbers."""
    user_points = [
        {"location": "message", "role": "system", "ttl": "1h"},
    ]
    llm = _FakeLLM(
        model_kwargs={"cache_control_injection_points": user_points},
    )

    apply_litellm_prompt_caching(llm)

    assert llm.model_kwargs["cache_control_injection_points"] is user_points


def test_idempotent_when_called_multiple_times() -> None:
    """Build-time + thread-time double-call must be a no-op the second time."""
    cfg = _make_cfg(provider="OPENAI")
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=1)
    snapshot = {
        "cache_control_injection_points": list(
            llm.model_kwargs["cache_control_injection_points"]
        ),
        "prompt_cache_key": llm.model_kwargs["prompt_cache_key"],
        "prompt_cache_retention": llm.model_kwargs["prompt_cache_retention"],
    }
    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=1)

    assert (
        llm.model_kwargs["cache_control_injection_points"]
        == snapshot["cache_control_injection_points"]
    )
    assert llm.model_kwargs["prompt_cache_key"] == snapshot["prompt_cache_key"]
    assert (
        llm.model_kwargs["prompt_cache_retention"] == snapshot["prompt_cache_retention"]
    )


def test_does_not_overwrite_user_supplied_prompt_cache_key() -> None:
    """A pre-set ``prompt_cache_key`` (e.g. tenant-aware override via
    ``litellm_params``) wins over our default per-thread key."""
    cfg = _make_cfg(provider="OPENAI")
    llm = _FakeLLM(model_kwargs={"prompt_cache_key": "tenant-abc"})

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=42)

    assert llm.model_kwargs["prompt_cache_key"] == "tenant-abc"


# ---------------------------------------------------------------------------
# (c) OpenAI-family extras (OPENAI / DEEPSEEK / XAI)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["OPENAI", "DEEPSEEK", "XAI"])
def test_sets_openai_family_extras(provider: str) -> None:
    """OpenAI-style providers gain ``prompt_cache_key`` (raises hit rate
    via routing affinity) and ``prompt_cache_retention="24h"`` (extends
    cache TTL beyond the default 5-10 min)."""
    cfg = _make_cfg(provider=provider)
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=42)

    assert llm.model_kwargs["prompt_cache_key"] == "surfsense-thread-42"
    assert llm.model_kwargs["prompt_cache_retention"] == "24h"


def test_skips_prompt_cache_key_when_no_thread_id() -> None:
    """Without a thread id we can't construct a per-thread key. Retention
    is still useful so we set it (it's free)."""
    cfg = _make_cfg(provider="OPENAI")
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=None)

    assert "prompt_cache_key" not in llm.model_kwargs
    assert llm.model_kwargs["prompt_cache_retention"] == "24h"


@pytest.mark.parametrize(
    "provider",
    ["ANTHROPIC", "BEDROCK", "VERTEX_AI", "GOOGLE_AI_STUDIO", "GROQ", "MOONSHOT"],
)
def test_no_openai_extras_for_other_providers(provider: str) -> None:
    """Non-OpenAI-family providers don't expose ``prompt_cache_key`` —
    skip it. ``cache_control_injection_points`` is still set (universal)."""
    cfg = _make_cfg(provider=provider)
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=42)

    assert "prompt_cache_key" not in llm.model_kwargs
    assert "prompt_cache_retention" not in llm.model_kwargs
    assert "cache_control_injection_points" in llm.model_kwargs


def test_no_openai_extras_in_auto_mode() -> None:
    """Auto-mode fans out across mixed providers — we can't statically
    target OpenAI-only kwargs."""
    cfg = AgentConfig.from_auto_mode()
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=42)

    assert "prompt_cache_key" not in llm.model_kwargs
    assert "prompt_cache_retention" not in llm.model_kwargs
    assert "cache_control_injection_points" in llm.model_kwargs


def test_no_openai_extras_for_custom_provider() -> None:
    """Custom providers route through arbitrary user-supplied prefixes —
    we don't try to infer OpenAI-family compatibility."""
    cfg = _make_cfg(provider="OPENAI", custom_provider="my_proxy")
    llm = _FakeLLM()

    apply_litellm_prompt_caching(llm, agent_config=cfg, thread_id=42)

    assert "prompt_cache_key" not in llm.model_kwargs
    assert "prompt_cache_retention" not in llm.model_kwargs


# ---------------------------------------------------------------------------
# (d) ChatLiteLLMRouter — universal injection points only
# ---------------------------------------------------------------------------


def test_router_llm_gets_only_universal_injection_points() -> None:
    """Even with an OpenAI-flavoured config, a ``ChatLiteLLMRouter`` must
    receive only the universal injection points — its requests dispatch
    across provider deployments and OpenAI-only kwargs would be wasted
    (or stripped by ``drop_params``) on non-OpenAI legs."""
    router = ChatLiteLLMRouter()
    cfg = _make_cfg(provider="OPENAI")

    apply_litellm_prompt_caching(router, agent_config=cfg, thread_id=42)

    assert "cache_control_injection_points" in router.model_kwargs
    assert "prompt_cache_key" not in router.model_kwargs
    assert "prompt_cache_retention" not in router.model_kwargs


# ---------------------------------------------------------------------------
# (e) Defensive paths
# ---------------------------------------------------------------------------


def test_handles_llm_with_no_writable_model_kwargs() -> None:
    """Some LLM implementations (e.g. fakes / minimal subclasses) don't
    expose a writable ``model_kwargs``. The helper must skip silently —
    raising would crash the entire LLM build path on a non-critical
    optimisation."""

    class _ImmutableLLM:
        # ``__slots__`` blocks attribute creation, so ``setattr`` raises.
        __slots__ = ("model",)

        def __init__(self) -> None:
            self.model = "openai/gpt-4o"

    llm = _ImmutableLLM()

    apply_litellm_prompt_caching(llm)


def test_initialises_missing_model_kwargs_dict() -> None:
    """When ``model_kwargs`` is present-but-None (Pydantic v2 default
    pattern when no factory is set), the helper initialises it to an
    empty dict before mutating."""

    class _LazyLLM:
        def __init__(self) -> None:
            self.model = "openai/gpt-4o"
            self.model_kwargs: dict[str, Any] | None = None

    llm = _LazyLLM()

    apply_litellm_prompt_caching(llm)

    assert isinstance(llm.model_kwargs, dict)
    assert "cache_control_injection_points" in llm.model_kwargs


def test_falls_back_to_llm_model_prefix_when_no_agent_config() -> None:
    """Direct caller path (e.g. ``create_chat_litellm_from_config`` for
    YAML configs without a structured ``AgentConfig``): without
    ``agent_config`` the helper sets only the universal injection points
    — no OpenAI-family extras even if the prefix says ``openai/``.
    Conservative: we'd rather miss the speedup than silently misroute."""
    llm = _FakeLLM(model="openai/gpt-4o")

    apply_litellm_prompt_caching(llm, agent_config=None, thread_id=99)

    assert "cache_control_injection_points" in llm.model_kwargs
    assert "prompt_cache_key" not in llm.model_kwargs
    assert "prompt_cache_retention" not in llm.model_kwargs


# ---------------------------------------------------------------------------
# (f) drop_params safety net (regression guard for #19346)
# ---------------------------------------------------------------------------


def test_litellm_drop_params_is_globally_enabled() -> None:
    """``litellm.drop_params=True`` is set globally in
    :mod:`app.services.llm_service` so any ``prompt_cache_key`` /
    ``prompt_cache_retention`` we set on an OpenAI-family config is
    auto-stripped if the request later routes to a non-supporting
    provider (e.g. via auto-mode router fallback). This test pins that
    invariant — losing it would mean Bedrock/Vertex 400s on ``prompt_cache_key``.
    """
    import litellm

    import app.services.llm_service  # noqa: F401  (side-effect: sets globals)

    assert litellm.drop_params is True


# ---------------------------------------------------------------------------
# Regression note: LiteLLM #15696 (multi-content-block last message)
# ---------------------------------------------------------------------------
#
# Before LiteLLM 1.81 a list-form last message ``[block_a, block_b]``
# would get ``cache_control`` applied to *every* content block instead
# of only the last one — wasting cache breakpoints and triggering 400s
# on Anthropic when it exceeded the 4-breakpoint limit. Fixed in
# https://github.com/BerriAI/litellm/pull/15699.
#
# We pin ``litellm>=1.83.7`` in ``pyproject.toml`` (well past the fix).
# An end-to-end behavioural test would need to run ``litellm.completion``
# through the Anthropic transformer, which is integration territory and
# better covered by LiteLLM's own test suite. The unit guard here is the
# version pin plus the build-time ``model_kwargs`` shape we verify above.
