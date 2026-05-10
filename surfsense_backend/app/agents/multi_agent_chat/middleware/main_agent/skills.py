"""Skill discovery + injection."""

from __future__ import annotations

import logging

from deepagents.middleware.skills import SkillsMiddleware

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import (
    build_skills_backend_factory,
    default_skills_sources,
)

from ..shared.flags import enabled


def build_skills_mw(
    *,
    flags: AgentFeatureFlags,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
) -> SkillsMiddleware | None:
    if not enabled(flags, "enable_skills"):
        return None
    try:
        skills_factory = build_skills_backend_factory(
            search_space_id=search_space_id
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
