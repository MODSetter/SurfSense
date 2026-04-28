"""``GET /api/agent/flags``: read-only feature-flag status.

Surfaces :class:`AgentFeatureFlags` to the frontend so the UI can:

* Render conditional surfaces (e.g. show the action-log button only when
  ``enable_action_log`` is on).
* Display an admin diagnostics card so operators can verify which
  middleware tier is active without shelling into the box.

The endpoint is *read-only*. Flipping flags requires an env-var change
plus a process restart — by design, since the values are baked into the
agent factory at build time. The route does not require any special
permission (any authenticated user can see them) since the flag values
do not leak data, and the UI surfaces are conditionally rendered based
on them anyway.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.new_chat.feature_flags import AgentFeatureFlags, get_flags
from app.db import User
from app.users import current_active_user

router = APIRouter()


class AgentFeatureFlagsRead(BaseModel):
    """Mirror of :class:`AgentFeatureFlags`. Updated together with it."""

    disable_new_agent_stack: bool

    enable_context_editing: bool
    enable_compaction_v2: bool
    enable_retry_after: bool
    enable_model_fallback: bool
    enable_model_call_limit: bool
    enable_tool_call_limit: bool
    enable_tool_call_repair: bool
    enable_doom_loop: bool

    enable_permission: bool
    enable_busy_mutex: bool
    enable_llm_tool_selector: bool

    enable_skills: bool
    enable_specialized_subagents: bool
    enable_kb_planner_runnable: bool

    enable_action_log: bool
    enable_revert_route: bool

    enable_plugin_loader: bool

    enable_otel: bool

    @classmethod
    def from_flags(cls, flags: AgentFeatureFlags) -> "AgentFeatureFlagsRead":
        # asdict() avoids missing-field bugs when AgentFeatureFlags grows.
        return cls(**asdict(flags))


@router.get("/agent/flags", response_model=AgentFeatureFlagsRead)
async def get_agent_flags(
    _user: User = Depends(current_active_user),
) -> AgentFeatureFlagsRead:
    return AgentFeatureFlagsRead.from_flags(get_flags())
