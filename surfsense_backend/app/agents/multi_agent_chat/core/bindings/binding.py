"""Shared kwargs dict for ``new_chat`` tool factories (DB session + search space + user)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


def connector_binding(
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
) -> dict[str, AsyncSession | int | str]:
    return {
        "db_session": db_session,
        "search_space_id": search_space_id,
        "user_id": user_id,
    }
