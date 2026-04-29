"""Resolve and persist Auto (Fastest) model pins per chat thread.

Auto (Fastest) is represented by ``agent_llm_id == 0``. For chat threads we
resolve that virtual mode to one concrete global LLM config exactly once and
persist the chosen config id on ``new_chat_threads`` so subsequent turns are
stable.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import NewChatThread
from app.services.token_quota_service import TokenQuotaService

logger = logging.getLogger(__name__)

AUTO_FASTEST_ID = 0
AUTO_FASTEST_MODE = "auto_fastest"


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


def _global_candidates() -> list[dict]:
    candidates = [cfg for cfg in config.GLOBAL_LLM_CONFIGS if _is_usable_global_config(cfg)]
    return sorted(candidates, key=lambda c: int(c.get("id", 0)))


def _tier_of(cfg: dict) -> str:
    return str(cfg.get("billing_tier", "free")).lower()


def _deterministic_pick(candidates: list[dict], thread_id: int) -> dict:
    digest = hashlib.sha256(f"{AUTO_FASTEST_MODE}:{thread_id}".encode()).digest()
    idx = int.from_bytes(digest[:8], "big") % len(candidates)
    return candidates[idx]


def _to_uuid(user_id: str | UUID | None) -> UUID | None:
    if user_id is None:
        return None
    if isinstance(user_id, UUID):
        return user_id
    try:
        return UUID(str(user_id))
    except Exception:
        return None


async def _is_premium_eligible(session: AsyncSession, user_id: str | UUID | None) -> bool:
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
) -> AutoPinResolution:
    """Resolve Auto (Fastest) to one concrete config id and persist pin metadata.

    For non-auto selections, this function clears existing auto pin metadata and
    returns the selected id as-is.
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

    # Explicit model selected: clear stale auto pin metadata.
    if selected_llm_config_id != AUTO_FASTEST_ID:
        if (
            thread.pinned_llm_config_id is not None
            or thread.pinned_auto_mode is not None
            or thread.pinned_at is not None
        ):
            thread.pinned_llm_config_id = None
            thread.pinned_auto_mode = None
            thread.pinned_at = None
            await session.commit()
        return AutoPinResolution(
            resolved_llm_config_id=selected_llm_config_id,
            resolved_tier="explicit",
            from_existing_pin=False,
        )

    candidates = _global_candidates()
    if not candidates:
        raise ValueError("No usable global LLM configs are available for Auto mode")
    candidate_by_id = {int(c["id"]): c for c in candidates}

    # Reuse existing valid pin without re-checking current quota (no silent tier switch),
    # unless the caller explicitly requests a forced repin to free.
    pinned_id = thread.pinned_llm_config_id
    if (
        not force_repin_free
        and
        thread.pinned_auto_mode == AUTO_FASTEST_MODE
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
        return AutoPinResolution(
            resolved_llm_config_id=int(pinned_id),
            resolved_tier=_tier_of(pinned_cfg),
            from_existing_pin=True,
        )
    if pinned_id is not None:
        logger.info(
            "auto_pin_invalid thread_id=%s search_space_id=%s pinned_config_id=%s pinned_auto_mode=%s",
            thread_id,
            search_space_id,
            pinned_id,
            thread.pinned_auto_mode,
        )

    premium_eligible = False if force_repin_free else await _is_premium_eligible(session, user_id)
    if premium_eligible:
        eligible = candidates
    else:
        eligible = [c for c in candidates if _tier_of(c) != "premium"]

    if not eligible:
        raise ValueError(
            "Auto mode could not find an eligible LLM config for this user and quota state"
        )

    selected_cfg = _deterministic_pick(eligible, thread_id)
    selected_id = int(selected_cfg["id"])
    selected_tier = _tier_of(selected_cfg)

    thread.pinned_llm_config_id = selected_id
    thread.pinned_auto_mode = AUTO_FASTEST_MODE
    thread.pinned_at = datetime.now(UTC)
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
    return AutoPinResolution(
        resolved_llm_config_id=selected_id,
        resolved_tier=selected_tier,
        from_existing_pin=False,
    )
