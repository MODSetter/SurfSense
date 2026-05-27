"""``ActionDefinition``, ``ActionContext``, and handler/factory signatures."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Per-invocation dependencies bound to an action handler at execute time."""

    session: AsyncSession
    run_id: int
    step_id: str
    search_space_id: int
    creator_user_id: UUID | None


ActionHandler = Callable[[dict[str, Any]], Awaitable[Any]]
ActionHandlerFactory = Callable[[ActionContext], ActionHandler]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    type: str
    name: str
    description: str
    params_schema: dict[str, Any]
    build_handler: ActionHandlerFactory
