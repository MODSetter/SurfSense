"""Authorization invariants for gateway-routed turns."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import GatewayConversationBinding, Permission, User
from app.gateway.bindings import suspend_binding
from app.observability.metrics import record_gateway_auth_invariant_failure
from app.utils.rbac import check_permission, check_search_space_access


class GatewaySuspendedError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def _fail(
    session: AsyncSession,
    binding: GatewayConversationBinding,
    reason: str,
) -> None:
    suspend_binding(binding, reason)
    record_gateway_auth_invariant_failure(cause=reason)
    await session.flush()
    raise GatewaySuspendedError(reason)


async def assert_authorization_invariant(
    session: AsyncSession,
    binding: GatewayConversationBinding,
) -> User:
    if binding.state != "bound":
        await _fail(session, binding, "binding_not_bound")

    user = await session.get(User, binding.user_id)
    if user is None:
        await _fail(session, binding, "owner_missing")

    try:
        await check_search_space_access(session, user, binding.search_space_id)
        await check_permission(
            session,
            user,
            binding.search_space_id,
            Permission.CHATS_CREATE.value,
            "Gateway owner no longer has permission to chat in this search space",
        )
    except HTTPException as exc:
        await _fail(session, binding, f"rbac_{exc.status_code}")

    return user

