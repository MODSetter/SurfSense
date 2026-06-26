"""Skill discovery + injection."""

from __future__ import annotations

import logging

from deepagents.middleware.skills import SkillsMiddleware

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.shared.middleware.flags import enabled

from ..skills.backends import build_skills_backend_factory, default_skills_sources


def build_skills_mw(
    *,
    flags: AgentFeatureFlags,
    filesystem_mode: FilesystemMode,
    workspace_id: int,
) -> SkillsMiddleware | None:
    if not enabled(flags, "enable_skills"):
        return None
    try:
        skills_factory = build_skills_backend_factory(
            workspace_id=workspace_id
            if filesystem_mode == FilesystemMode.CLOUD
            else None,
        )
        return SkillsMiddleware(
            backend=skills_factory,
            sources=default_skills_sources(),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("SkillsMiddleware init failed; skipping: %s", exc)
        return None
