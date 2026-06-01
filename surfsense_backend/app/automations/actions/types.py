"""``ActionDefinition``, ``ActionContext``, and handler/factory signatures."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Per-invocation dependencies bound to an action handler at execute time."""

    session: AsyncSession
    run_id: int
    step_id: str
    search_space_id: int
    creator_user_id: UUID | None
    # Captured model snapshot from the automation definition (``definition.models``),
    # resolved per run instead of the live search space. ``None`` falls back to the
    # search space's current prefs (defensive; should not happen post-capture).
    agent_llm_id: int | None = None
    image_generation_config_id: int | None = None
    vision_llm_config_id: int | None = None


ActionHandler = Callable[[dict[str, Any]], Awaitable[Any]]
ActionHandlerFactory = Callable[[ActionContext], ActionHandler]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    type: str
    name: str
    description: str
    params_model: type[BaseModel]
    build_handler: ActionHandlerFactory

    @property
    def params_schema(self) -> dict[str, Any]:
        """JSON Schema (draft 2020-12) derived from ``params_model``."""
        return self.params_model.model_json_schema()
