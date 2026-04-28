"""CRUD for :class:`app.db.AgentPermissionRule`.

Surfaces the permission rules consumed by
:class:`PermissionMiddleware`. Rules are scoped at one of three levels:

* **Search-space wide** — both ``user_id`` and ``thread_id`` are NULL.
* **Per-user** — ``user_id`` set, ``thread_id`` NULL.
* **Per-thread** — ``thread_id`` set (``user_id`` typically NULL).

The middleware reads these rows at agent build time (see
``chat_deepagent.py``). UI lets a search-space owner curate them so
the agent can ask for approval / auto-deny / auto-allow specific
tool patterns.

The route group is gated by ``SURFSENSE_ENABLE_PERMISSION``: when off
all endpoints return 503 so the UI can render a "feature not enabled"
empty state without breaking on a missing route.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.feature_flags import get_flags
from app.db import (
    AgentPermissionRule,
    NewChatThread,
    Permission,
    SearchSpace,
    User,
    get_async_session,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


_ACTION_VALUES: tuple[str, ...] = ("allow", "deny", "ask")
_PERMISSION_PATTERN = re.compile(r"^[a-zA-Z0-9_:.\-*]+$")


class AgentPermissionRuleRead(BaseModel):
    id: int
    search_space_id: int
    user_id: str | None
    thread_id: int | None
    permission: str
    pattern: str
    action: Literal["allow", "deny", "ask"]
    created_at: datetime


class AgentPermissionRuleCreate(BaseModel):
    permission: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Tool / capability the rule targets, e.g. 'tool:create_linear_issue'.",
    )
    pattern: str = Field(
        "*",
        min_length=1,
        max_length=255,
        description="Wildcard pattern (e.g. '*' or 'production-*') applied to the matched tool argument.",
    )
    action: Literal["allow", "deny", "ask"]
    user_id: str | None = None
    thread_id: int | None = None


class AgentPermissionRuleUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=255)
    action: Literal["allow", "deny", "ask"] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flag_guard() -> None:
    flags = get_flags()
    if flags.disable_new_agent_stack or not flags.enable_permission:
        raise HTTPException(
            status_code=503,
            detail=(
                "Agent permission rules are not enabled on this deployment. "
                "Flip SURFSENSE_ENABLE_PERMISSION to enable them."
            ),
        )


def _validate_permission_string(value: str) -> str:
    if not _PERMISSION_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=(
                "permission must contain only alphanumerics, '.', '_', ':', '-', "
                "or '*' wildcards."
            ),
        )
    return value


def _to_read(row: AgentPermissionRule) -> AgentPermissionRuleRead:
    return AgentPermissionRuleRead(
        id=row.id,
        search_space_id=row.search_space_id,
        user_id=str(row.user_id) if row.user_id is not None else None,
        thread_id=row.thread_id,
        permission=row.permission,
        pattern=row.pattern,
        action=row.action,  # type: ignore[arg-type]
        created_at=row.created_at,
    )


async def _ensure_search_space_membership_admin(
    session: AsyncSession, user: User, search_space_id: int
) -> None:
    """Curating agent rules == "settings" administration on the space."""
    space = await session.get(SearchSpace, search_space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Search space not found.")
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.SETTINGS_UPDATE.value,
        "You don't have permission to manage agent permission rules in this space.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/searchspaces/{search_space_id}/agent/permissions/rules",
    response_model=list[AgentPermissionRuleRead],
)
async def list_rules(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> list[AgentPermissionRuleRead]:
    _flag_guard()
    await _ensure_search_space_membership_admin(session, user, search_space_id)

    stmt = (
        select(AgentPermissionRule)
        .where(AgentPermissionRule.search_space_id == search_space_id)
        .order_by(AgentPermissionRule.created_at.desc(), AgentPermissionRule.id.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_read(r) for r in rows]


@router.post(
    "/searchspaces/{search_space_id}/agent/permissions/rules",
    response_model=AgentPermissionRuleRead,
    status_code=201,
)
async def create_rule(
    search_space_id: int,
    payload: AgentPermissionRuleCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> AgentPermissionRuleRead:
    _flag_guard()
    await _ensure_search_space_membership_admin(session, user, search_space_id)

    permission = _validate_permission_string(payload.permission.strip())
    pattern = payload.pattern.strip() or "*"

    if payload.thread_id is not None:
        thread = await session.get(NewChatThread, payload.thread_id)
        if thread is None or thread.search_space_id != search_space_id:
            raise HTTPException(
                status_code=404,
                detail="Thread not found in this search space.",
            )

    row = AgentPermissionRule(
        search_space_id=search_space_id,
        user_id=payload.user_id,
        thread_id=payload.thread_id,
        permission=permission,
        pattern=pattern,
        action=payload.action,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "An identical rule already exists for this scope. Update the "
                "existing rule instead."
            ),
        )
    await session.refresh(row)
    return _to_read(row)


@router.patch(
    "/searchspaces/{search_space_id}/agent/permissions/rules/{rule_id}",
    response_model=AgentPermissionRuleRead,
)
async def update_rule(
    search_space_id: int,
    rule_id: int,
    payload: AgentPermissionRuleUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> AgentPermissionRuleRead:
    _flag_guard()
    await _ensure_search_space_membership_admin(session, user, search_space_id)

    row = await session.get(AgentPermissionRule, rule_id)
    if row is None or row.search_space_id != search_space_id:
        raise HTTPException(status_code=404, detail="Rule not found.")

    if payload.pattern is not None:
        row.pattern = payload.pattern.strip() or "*"
    if payload.action is not None:
        row.action = payload.action

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Update would create a duplicate rule for this scope.",
        )
    await session.refresh(row)
    return _to_read(row)


@router.delete(
    "/searchspaces/{search_space_id}/agent/permissions/rules/{rule_id}",
    status_code=204,
)
async def delete_rule(
    search_space_id: int,
    rule_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> None:
    _flag_guard()
    await _ensure_search_space_membership_admin(session, user, search_space_id)

    row = await session.get(AgentPermissionRule, rule_id)
    if row is None or row.search_space_id != search_space_id:
        raise HTTPException(status_code=404, detail="Rule not found.")

    await session.delete(row)
    await session.commit()
    return None
