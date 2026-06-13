"""Resolve and persist Auto model pins per chat thread.

Auto is represented by ``chat_model_id == 0``. For chat threads we
resolve that virtual mode to one concrete global model exactly once and
persist the chosen config id on ``new_chat_threads.pinned_llm_config_id`` so
subsequent turns are stable.

Single-writer invariant: this module is the only writer of
``NewChatThread.pinned_llm_config_id`` (aside from the bulk clear in
``model_connections_routes`` when a search space's ``chat_model_id`` changes).
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

import redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import Connection, Model, NewChatThread
from app.services.model_capabilities import has_capability
from app.services.quality_score import _QUALITY_TOP_K
from app.services.token_quota_service import TokenQuotaService

logger = logging.getLogger(__name__)

AUTO_MODE_ID = 0
# Stable internal hash namespace for deterministic per-thread selection.
# Do not rename: changing this rebalances Auto's model choice for new pins.
AUTO_PIN_HASH_NAMESPACE = "auto_fastest"
_RUNTIME_COOLDOWN_SECONDS = 600
_HEALTHY_TTL_SECONDS = 45
_RUNTIME_COOLDOWN_REDIS_KEY_PREFIX = "auto:cooldown:llm:"
_REDIS_TIMEOUT_SECONDS = 0.2

# In-memory runtime cooldown map for configs that recently hard-failed at
# provider runtime (e.g. OpenRouter 429 on a pinned free model). This keeps
# the same unhealthy config from being reselected immediately during repair.
_runtime_cooldown_until: dict[int, float] = {}
_runtime_cooldown_lock = threading.Lock()
_runtime_cooldown_redis: redis.Redis | None = None
_runtime_cooldown_redis_lock = threading.Lock()

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
        and (cfg.get("provider") or cfg.get("litellm_provider"))
        and cfg.get("api_key")
    )


def _has_capability(model: dict | Model, capability: str) -> bool:
    return has_capability(model, capability)


def _prune_runtime_cooldowns(now_ts: float | None = None) -> None:
    now = time.time() if now_ts is None else now_ts
    stale = [cid for cid, until in _runtime_cooldown_until.items() if until <= now]
    for cid in stale:
        _runtime_cooldown_until.pop(cid, None)


def _is_runtime_cooled_down(config_id: int) -> bool:
    with _runtime_cooldown_lock:
        _prune_runtime_cooldowns()
        return config_id in _runtime_cooldown_until


def _runtime_cooldown_redis_key(config_id: int) -> str:
    return f"{_RUNTIME_COOLDOWN_REDIS_KEY_PREFIX}{int(config_id)}"


def _get_runtime_cooldown_redis() -> redis.Redis:
    global _runtime_cooldown_redis
    if _runtime_cooldown_redis is None:
        with _runtime_cooldown_redis_lock:
            if _runtime_cooldown_redis is None:
                _runtime_cooldown_redis = redis.from_url(
                    config.REDIS_APP_URL,
                    decode_responses=True,
                    socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
                    socket_timeout=_REDIS_TIMEOUT_SECONDS,
                )
    return _runtime_cooldown_redis


def _mark_shared_runtime_cooldown(
    config_id: int,
    *,
    reason: str,
    cooldown_seconds: int,
) -> None:
    try:
        _get_runtime_cooldown_redis().set(
            _runtime_cooldown_redis_key(config_id),
            reason,
            ex=int(cooldown_seconds),
        )
    except Exception:
        logger.warning(
            "auto_pin_runtime_cooldown_redis_write_failed config_id=%s",
            config_id,
            exc_info=True,
        )


def _shared_runtime_cooled_down_ids(config_ids: list[int]) -> set[int]:
    unique_ids = list(dict.fromkeys(int(cid) for cid in config_ids))
    if not unique_ids:
        return set()
    try:
        values = _get_runtime_cooldown_redis().mget(
            [_runtime_cooldown_redis_key(cid) for cid in unique_ids]
        )
    except Exception:
        logger.warning(
            "auto_pin_runtime_cooldown_redis_read_failed count=%s",
            len(unique_ids),
            exc_info=True,
        )
        return set()
    return {cid for cid, value in zip(unique_ids, values, strict=False) if value is not None}


def _clear_shared_runtime_cooldown(config_id: int | None = None) -> None:
    try:
        client = _get_runtime_cooldown_redis()
        if config_id is not None:
            client.delete(_runtime_cooldown_redis_key(config_id))
            return
        keys = list(client.scan_iter(f"{_RUNTIME_COOLDOWN_REDIS_KEY_PREFIX}*"))
        if keys:
            client.delete(*keys)
    except Exception:
        logger.warning(
            "auto_pin_runtime_cooldown_redis_clear_failed config_id=%s",
            config_id,
            exc_info=True,
        )


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
    _mark_shared_runtime_cooldown(
        int(config_id),
        reason=reason,
        cooldown_seconds=int(cooldown_seconds),
    )
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
        else:
            _runtime_cooldown_until.pop(int(config_id), None)
    _clear_shared_runtime_cooldown(config_id)


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
        provider=cfg.get("provider") or cfg.get("litellm_provider"),
        model_name=cfg.get("model_name"),
        base_model=base_model,
        custom_provider=cfg.get("custom_provider"),
    )


def _global_candidates(
    *,
    capability: str = "chat",
    requires_image_input: bool = False,
    shared_cooled_down_ids: set[int] | None = None,
) -> list[dict]:
    """Return Auto-eligible global virtual models.

    Drops cfgs flagged ``health_gated`` (best non-null OpenRouter uptime
    below ``_HEALTH_GATE_UPTIME_PCT``) so chronically broken providers
    can't be picked as the thread's pin. Also excludes configs currently
    in runtime cooldown (e.g. temporary 429 bursts).

    When ``requires_image_input`` is True (image turn), additionally
    filters out configs whose ``supports_image_input`` resolves to False
    so a text-only deployment can't be pinned for an image request.
    """
    connection_by_id = {
        int(conn.get("id")): conn
        for conn in config.GLOBAL_CONNECTIONS
        if conn.get("id") is not None
    }
    config_by_model_name = {
        cfg.get("model_name"): cfg
        for cfg in config.GLOBAL_LLM_CONFIGS
        if _is_usable_global_config(cfg)
    }
    candidates: list[dict] = []
    shared_cooled_down_ids = shared_cooled_down_ids or set()
    for model in config.GLOBAL_MODELS:
        model_id = int(model.get("id", 0))
        if (
            model_id >= 0
            or _is_runtime_cooled_down(model_id)
            or model_id in shared_cooled_down_ids
        ):
            continue
        if not _has_capability(model, capability):
            continue
        cfg = config_by_model_name.get(model.get("model_id")) or {}
        if cfg.get("health_gated"):
            continue
        if requires_image_input and not _has_capability(model, "vision"):
            continue
        if requires_image_input and cfg and not _cfg_supports_image_input(cfg):
            continue
        connection = connection_by_id.get(int(model.get("connection_id", 0)))
        if not connection:
            continue
        catalog = model.get("catalog") or {}
        candidates.append(
            {
                "id": model_id,
                "model_id": model.get("model_id"),
                "source": "global",
                "connection": connection,
                "supports_chat": model.get("supports_chat"),
                "supports_image_input": model.get("supports_image_input"),
                "supports_tools": model.get("supports_tools"),
                "supports_image_generation": model.get("supports_image_generation"),
                "capabilities_override": model.get("capabilities_override") or {},
                "billing_tier": model.get("billing_tier", "free"),
                "provider": connection.get("provider"),
                "model_name": model.get("model_id"),
                "auto_pin_tier": catalog.get("auto_pin_tier")
                or cfg.get("auto_pin_tier")
                or "A",
                "quality_score": catalog.get("quality_score")
                or cfg.get("quality_score")
                or cfg.get("quality_score_static")
                or 50,
            }
        )
    return sorted(candidates, key=lambda c: int(c.get("id", 0)))


async def _db_candidates(
    session: AsyncSession,
    *,
    search_space_id: int,
    user_id: str | UUID | None,
    capability: str,
    requires_image_input: bool = False,
) -> list[dict]:
    parsed_user_id = _to_uuid(user_id)
    stmt = (
        select(Model)
        .options(selectinload(Model.connection))
        .join(Connection, Model.connection_id == Connection.id)
        .where(Model.enabled.is_(True), Connection.enabled.is_(True))
    )
    result = await session.execute(stmt)
    models = result.scalars().all()
    shared_cooled_down_ids = _shared_runtime_cooled_down_ids(
        [int(model.id) for model in models]
    )
    candidates: list[dict] = []
    for model in models:
        conn = model.connection
        if not conn:
            continue
        if conn.search_space_id is not None and conn.search_space_id != search_space_id:
            continue
        if conn.user_id is not None and parsed_user_id is not None and conn.user_id != parsed_user_id:
            continue
        if conn.user_id is not None and parsed_user_id is None:
            continue
        if not _has_capability(model, capability):
            continue
        if requires_image_input and not _has_capability(model, "vision"):
            continue
        model_id = int(model.id)
        if _is_runtime_cooled_down(model_id) or model_id in shared_cooled_down_ids:
            continue
        catalog = model.catalog or {}
        candidates.append(
            {
                "id": model_id,
                "model_id": model.model_id,
                "source": "db",
                "connection": conn,
                "supports_chat": model.supports_chat,
                "supports_image_input": model.supports_image_input,
                "supports_tools": model.supports_tools,
                "supports_image_generation": model.supports_image_generation,
                "capabilities_override": model.capabilities_override or {},
                "billing_tier": "byok",
                "provider": conn.provider,
                "model_name": model.model_id,
                "auto_pin_tier": catalog.get("auto_pin_tier") or "BYOK",
                "quality_score": catalog.get("quality_score") or 75,
            }
        )
    return sorted(candidates, key=lambda c: int(c.get("id", 0)))


async def auto_model_candidates(
    session: AsyncSession,
    *,
    search_space_id: int,
    user_id: str | UUID | None,
    capability: str,
    requires_image_input: bool = False,
    exclude_model_ids: set[int] | None = None,
) -> list[dict]:
    excluded_ids = {int(mid) for mid in (exclude_model_ids or set())}
    global_ids = [
        int(model.get("id", 0))
        for model in config.GLOBAL_MODELS
        if int(model.get("id", 0)) < 0
    ]
    shared_global_cooled_down_ids = _shared_runtime_cooled_down_ids(global_ids)
    db_candidates = await _db_candidates(
        session,
        search_space_id=search_space_id,
        user_id=user_id,
        capability=capability,
        requires_image_input=requires_image_input,
    )
    candidates = [
        *_global_candidates(
            capability=capability,
            requires_image_input=requires_image_input,
            shared_cooled_down_ids=shared_global_cooled_down_ids,
        ),
        *db_candidates,
    ]
    return [c for c in candidates if int(c.get("id", 0)) not in excluded_ids]


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
    digest = hashlib.sha256(f"{AUTO_PIN_HASH_NAMESPACE}:{thread_id}".encode()).digest()
    idx = int.from_bytes(digest[:8], "big") % len(top_k)
    return top_k[idx], len(top_k)


def choose_auto_model_candidate(candidates: list[dict], seed_id: int) -> dict:
    selected, _ = _select_pin(candidates, seed_id)
    return selected


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
    usage = await TokenQuotaService.credit_get_usage(session, parsed)
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
    """Resolve Auto to one concrete config id and persist the pin.

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
    if selected_llm_config_id != AUTO_MODE_ID:
        if thread.pinned_llm_config_id is not None:
            thread.pinned_llm_config_id = None
            await session.commit()
        return AutoPinResolution(
            resolved_llm_config_id=selected_llm_config_id,
            resolved_tier="explicit",
            from_existing_pin=False,
        )

    excluded_ids = {int(cid) for cid in (exclude_config_ids or set())}
    candidates = await auto_model_candidates(
        session,
        search_space_id=search_space_id,
        user_id=user_id,
        capability="chat",
        requires_image_input=requires_image_input,
        exclude_model_ids=excluded_ids,
    )
    if not candidates:
        if requires_image_input:
            # Distinguish the "no vision-capable cfg" case from generic
            # "no usable cfg" so the streaming task can map this to the
            # MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT SSE error.
            raise ValueError(
                "No vision-capable LLM models are available for Auto mode"
            )
        raise ValueError("No usable LLM models are available for Auto mode")
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
    byok_candidates = [c for c in candidates if _tier_of(c) == "byok"]
    if premium_eligible:
        premium_candidates = [c for c in candidates if _tier_of(c) == "premium"]
        eligible = premium_candidates or byok_candidates
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
