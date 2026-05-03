"""Resolve and persist Auto (Fastest) model pins per chat thread.

Auto (Fastest) is represented by ``agent_llm_id == 0``. For chat threads we
resolve that virtual mode to one concrete global LLM config exactly once and
persist the chosen config id on ``new_chat_threads.pinned_llm_config_id`` so
subsequent turns are stable.

Single-writer invariant: this module is the only writer of
``NewChatThread.pinned_llm_config_id`` (aside from the bulk clear in
``search_spaces_routes`` when a search space's ``agent_llm_id`` changes).
Therefore a non-NULL value unambiguously means "this thread has an
Auto-resolved pin"; no separate source/policy column is needed.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import NewChatThread
from app.services.quality_score import _QUALITY_TOP_K
from app.services.token_quota_service import TokenQuotaService

logger = logging.getLogger(__name__)

AUTO_FASTEST_ID = 0
AUTO_FASTEST_MODE = "auto_fastest"
_RUNTIME_COOLDOWN_SECONDS = 600
_HEALTHY_TTL_SECONDS = 45

# In-memory runtime cooldown map for configs that recently hard-failed at
# provider runtime (e.g. OpenRouter 429 on a pinned free model). This keeps
# the same unhealthy config from being reselected immediately during repair.
_runtime_cooldown_until: dict[int, float] = {}
_runtime_cooldown_lock = threading.Lock()

# Short-TTL "recently healthy" cache for configs that just passed a runtime
# preflight ping. Lets back-to-back turns on the same model skip the probe
# without eroding correctness — entries auto-expire and are wiped any time
# the same config is cooled down or the OR catalogue is refreshed.
_healthy_until: dict[int, float] = {}
_healthy_lock = threading.Lock()


@dataclass
class AutoPinResolution:
    resolved_llm_config_id: int
    resolved_tier: str
    from_existing_pin: bool


def _is_usable_global_config(cfg: dict) -> bool:
    return bool(
        cfg.get("id") is not None
        and cfg.get("model_name")
        and cfg.get("provider")
        and cfg.get("api_key")
    )


def _prune_runtime_cooldowns(now_ts: float | None = None) -> None:
    now = time.time() if now_ts is None else now_ts
    stale = [cid for cid, until in _runtime_cooldown_until.items() if until <= now]
    for cid in stale:
        _runtime_cooldown_until.pop(cid, None)


def _is_runtime_cooled_down(config_id: int) -> bool:
    with _runtime_cooldown_lock:
        _prune_runtime_cooldowns()
        return config_id in _runtime_cooldown_until


def mark_runtime_cooldown(
    config_id: int,
    *,
    reason: str = "rate_limited",
    cooldown_seconds: int = _RUNTIME_COOLDOWN_SECONDS,
) -> None:
    """Temporarily suppress a config from Auto selection.

    Used by runtime error handlers (e.g. OpenRouter 429) so an already pinned
    config that is currently unhealthy does not get immediately reused on the
    same thread during repair.
    """
    if cooldown_seconds <= 0:
        cooldown_seconds = _RUNTIME_COOLDOWN_SECONDS
    until = time.time() + int(cooldown_seconds)
    with _runtime_cooldown_lock:
        _runtime_cooldown_until[int(config_id)] = until
        _prune_runtime_cooldowns()
    # A cooled cfg can never be "recently healthy"; drop any stale credit so
    # the next turn that resolves to it (after cooldown) re-runs preflight.
    clear_healthy(int(config_id))
    logger.info(
        "auto_pin_runtime_cooled_down config_id=%s reason=%s cooldown_seconds=%s",
        config_id,
        reason,
        cooldown_seconds,
    )


def clear_runtime_cooldown(config_id: int | None = None) -> None:
    """Test/ops helper to clear runtime cooldown entries."""
    with _runtime_cooldown_lock:
        if config_id is None:
            _runtime_cooldown_until.clear()
            return
        _runtime_cooldown_until.pop(int(config_id), None)


def _prune_healthy(now_ts: float | None = None) -> None:
    now = time.time() if now_ts is None else now_ts
    stale = [cid for cid, until in _healthy_until.items() if until <= now]
    for cid in stale:
        _healthy_until.pop(cid, None)


def is_recently_healthy(config_id: int) -> bool:
    """Return True if ``config_id`` passed preflight within the TTL window."""
    with _healthy_lock:
        _prune_healthy()
        return int(config_id) in _healthy_until


def mark_healthy(
    config_id: int,
    *,
    ttl_seconds: int = _HEALTHY_TTL_SECONDS,
) -> None:
    """Record that ``config_id`` just passed a preflight probe.

    Subsequent calls within ``ttl_seconds`` can skip the preflight ping. The
    healthy state is intentionally process-local — it's a latency hint, not a
    correctness primitive — so multi-worker drift is acceptable.
    """
    if ttl_seconds <= 0:
        ttl_seconds = _HEALTHY_TTL_SECONDS
    until = time.time() + int(ttl_seconds)
    with _healthy_lock:
        _healthy_until[int(config_id)] = until
        _prune_healthy()


def clear_healthy(config_id: int | None = None) -> None:
    """Drop one (or all) healthy-cache entries.

    Called from runtime cooldown and OR catalogue refresh so a freshly cooled
    or replaced config never carries stale "healthy" credit.
    """
    with _healthy_lock:
        if config_id is None:
            _healthy_until.clear()
            return
        _healthy_until.pop(int(config_id), None)


def _cfg_supports_image_input(cfg: dict) -> bool:
    """True if the global cfg can accept image inputs.

    Prefers the explicit ``supports_image_input`` flag (set by the YAML
    loader / OpenRouter integration). Falls back to a LiteLLM lookup so
    a YAML entry whose flag was somehow stripped doesn't get wrongly
    excluded. Default-allows on unknown — the streaming-task safety net
    is the actual block, not this filter.
    """
    if "supports_image_input" in cfg:
        return bool(cfg.get("supports_image_input"))
    # Lazy import: provider_capabilities -> llm_config -> services chain;
    # importing at module load would create an init-order cycle through
    # ``app.config``.
    from app.services.provider_capabilities import derive_supports_image_input

    cfg_litellm_params = cfg.get("litellm_params") or {}
    base_model = (
        cfg_litellm_params.get("base_model")
        if isinstance(cfg_litellm_params, dict)
        else None
    )
    return derive_supports_image_input(
        provider=cfg.get("provider"),
        model_name=cfg.get("model_name"),
        base_model=base_model,
        custom_provider=cfg.get("custom_provider"),
    )


def _global_candidates(*, requires_image_input: bool = False) -> list[dict]:
    """Return Auto-eligible global cfgs.

    Drops cfgs flagged ``health_gated`` (best non-null OpenRouter uptime
    below ``_HEALTH_GATE_UPTIME_PCT``) so chronically broken providers
    can't be picked as the thread's pin. Also excludes configs currently
    in runtime cooldown (e.g. temporary 429 bursts).

    When ``requires_image_input`` is True (image turn), additionally
    filters out configs whose ``supports_image_input`` resolves to False
    so a text-only deployment can't be pinned for an image request.
    """
    candidates = [
        cfg
        for cfg in config.GLOBAL_LLM_CONFIGS
        if _is_usable_global_config(cfg)
        and not cfg.get("health_gated")
        and not _is_runtime_cooled_down(int(cfg.get("id", 0)))
        and (not requires_image_input or _cfg_supports_image_input(cfg))
    ]
    return sorted(candidates, key=lambda c: int(c.get("id", 0)))


def _tier_of(cfg: dict) -> str:
    return str(cfg.get("billing_tier", "free")).lower()


def _select_pin(eligible: list[dict], thread_id: int) -> tuple[dict, int]:
    """Pick a config with quality-first ranking + deterministic spread.

    Tier policy is lock-first: prefer Tier A (operator-curated YAML)
    cfgs and only fall through to Tier B/C (dynamic OpenRouter) if no
    Tier A cfg is eligible after upstream filters. Within the locked
    pool, sort by ``quality_score`` and pick from the top-K via
    ``SHA256(thread_id)`` so different new threads spread across the
    best models without ever picking a low-ranked one.

    Returns ``(chosen_cfg, top_k_size)``. ``top_k_size`` is exposed for
    structured logging in the caller.
    """
    tier_a = [c for c in eligible if c.get("auto_pin_tier") in (None, "A")]
    pool = tier_a if tier_a else eligible
    pool = sorted(pool, key=lambda c: -int(c.get("quality_score") or 0))
    top_k = pool[:_QUALITY_TOP_K]
    digest = hashlib.sha256(f"{AUTO_FASTEST_MODE}:{thread_id}".encode()).digest()
    idx = int.from_bytes(digest[:8], "big") % len(top_k)
    return top_k[idx], len(top_k)


def _to_uuid(user_id: str | UUID | None) -> UUID | None:
    if user_id is None:
        return None
    if isinstance(user_id, UUID):
        return user_id
    try:
        return UUID(str(user_id))
    except Exception:
        return None


async def _is_premium_eligible(
    session: AsyncSession, user_id: str | UUID | None
) -> bool:
    parsed = _to_uuid(user_id)
    if parsed is None:
        return False
    usage = await TokenQuotaService.premium_get_usage(session, parsed)
    return bool(usage.allowed)


async def resolve_or_get_pinned_llm_config_id(
    session: AsyncSession,
    *,
    thread_id: int,
    search_space_id: int,
    user_id: str | UUID | None,
    selected_llm_config_id: int,
    force_repin_free: bool = False,
    exclude_config_ids: set[int] | None = None,
    requires_image_input: bool = False,
) -> AutoPinResolution:
    """Resolve Auto (Fastest) to one concrete config id and persist the pin.

    For non-auto selections, this function clears any existing pin and returns
    the selected id as-is.

    When ``requires_image_input`` is True (the current turn carries an
    ``image_url`` block), the candidate pool is filtered to vision-capable
    cfgs and any existing pin that can't accept image input is treated as
    invalid (force re-pin). If no vision-capable cfg is available the
    function raises ``ValueError`` so the streaming task surfaces the same
    friendly ``MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT`` error instead of
    silently routing the image to a text-only deployment.
    """
    thread = (
        (
            await session.execute(
                select(NewChatThread)
                .where(NewChatThread.id == thread_id)
                .with_for_update(of=NewChatThread)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    if thread.search_space_id != search_space_id:
        raise ValueError(
            f"Thread {thread_id} does not belong to search space {search_space_id}"
        )

    # Explicit model selected: clear any stale pin.
    if selected_llm_config_id != AUTO_FASTEST_ID:
        if thread.pinned_llm_config_id is not None:
            thread.pinned_llm_config_id = None
            await session.commit()
        return AutoPinResolution(
            resolved_llm_config_id=selected_llm_config_id,
            resolved_tier="explicit",
            from_existing_pin=False,
        )

    excluded_ids = {int(cid) for cid in (exclude_config_ids or set())}
    candidates = [
        c
        for c in _global_candidates(requires_image_input=requires_image_input)
        if int(c.get("id", 0)) not in excluded_ids
    ]
    if not candidates:
        if requires_image_input:
            # Distinguish the "no vision-capable cfg" case from generic
            # "no usable cfg" so the streaming task can map this to the
            # MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT SSE error.
            raise ValueError(
                "No vision-capable global LLM configs are available for Auto mode"
            )
        raise ValueError("No usable global LLM configs are available for Auto mode")
    candidate_by_id = {int(c["id"]): c for c in candidates}

    # Reuse an existing valid pin without re-checking current quota (no silent
    # tier switch), unless the caller explicitly requests a forced repin to free
    # *or* the turn requires image input but the pin can't handle it.
    pinned_id = thread.pinned_llm_config_id
    if (
        not force_repin_free
        and pinned_id is not None
        and int(pinned_id) in candidate_by_id
    ):
        pinned_cfg = candidate_by_id[int(pinned_id)]
        logger.info(
            "auto_pin_reused thread_id=%s search_space_id=%s resolved_config_id=%s tier=%s",
            thread_id,
            search_space_id,
            pinned_id,
            _tier_of(pinned_cfg),
        )
        logger.info(
            "auto_pin_resolved thread_id=%s config_id=%s tier=%s "
            "auto_pin_tier=%s score=%s top_k_size=0 from_existing_pin=True",
            thread_id,
            pinned_id,
            _tier_of(pinned_cfg),
            pinned_cfg.get("auto_pin_tier", "?"),
            int(pinned_cfg.get("quality_score") or 0),
        )
        return AutoPinResolution(
            resolved_llm_config_id=int(pinned_id),
            resolved_tier=_tier_of(pinned_cfg),
            from_existing_pin=True,
        )
    if pinned_id is not None:
        # If the pin is *only* invalid because it can't handle the image
        # turn (it's still a healthy, usable config in the broader pool),
        # log that explicitly so operators can correlate the re-pin with
        # the user's image attachment instead of suspecting a cooldown.
        if requires_image_input:
            try:
                pinned_global = next(
                    c
                    for c in config.GLOBAL_LLM_CONFIGS
                    if int(c.get("id", 0)) == int(pinned_id)
                )
            except StopIteration:
                pinned_global = None
            if pinned_global is not None and not _cfg_supports_image_input(
                pinned_global
            ):
                logger.info(
                    "auto_pin_repinned_for_image thread_id=%s search_space_id=%s "
                    "previous_config_id=%s",
                    thread_id,
                    search_space_id,
                    pinned_id,
                )
        logger.info(
            "auto_pin_invalid thread_id=%s search_space_id=%s pinned_config_id=%s",
            thread_id,
            search_space_id,
            pinned_id,
        )

    premium_eligible = (
        False if force_repin_free else await _is_premium_eligible(session, user_id)
    )
    if premium_eligible:
        eligible = candidates
    else:
        eligible = [c for c in candidates if _tier_of(c) != "premium"]

    if not eligible:
        if requires_image_input:
            raise ValueError(
                "Auto mode could not find a vision-capable LLM config for this user and quota state"
            )
        raise ValueError(
            "Auto mode could not find an eligible LLM config for this user and quota state"
        )

    selected_cfg, top_k_size = _select_pin(eligible, thread_id)
    selected_id = int(selected_cfg["id"])
    selected_tier = _tier_of(selected_cfg)

    thread.pinned_llm_config_id = selected_id
    await session.commit()

    if force_repin_free:
        logger.info(
            "auto_pin_forced_free_repin thread_id=%s search_space_id=%s previous_config_id=%s resolved_config_id=%s",
            thread_id,
            search_space_id,
            pinned_id,
            selected_id,
        )

    if pinned_id is None:
        logger.info(
            "auto_pin_created thread_id=%s search_space_id=%s resolved_config_id=%s tier=%s premium_eligible=%s",
            thread_id,
            search_space_id,
            selected_id,
            selected_tier,
            premium_eligible,
        )
    else:
        logger.info(
            "auto_pin_repaired thread_id=%s search_space_id=%s previous_config_id=%s resolved_config_id=%s tier=%s premium_eligible=%s",
            thread_id,
            search_space_id,
            pinned_id,
            selected_id,
            selected_tier,
            premium_eligible,
        )

    logger.info(
        "auto_pin_resolved thread_id=%s config_id=%s tier=%s "
        "auto_pin_tier=%s score=%s top_k_size=%d from_existing_pin=False",
        thread_id,
        selected_id,
        selected_tier,
        selected_cfg.get("auto_pin_tier", "?"),
        int(selected_cfg.get("quality_score") or 0),
        top_k_size,
    )

    return AutoPinResolution(
        resolved_llm_config_id=selected_id,
        resolved_tier=selected_tier,
        from_existing_pin=False,
    )
