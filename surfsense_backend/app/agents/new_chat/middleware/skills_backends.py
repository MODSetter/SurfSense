"""Backward-compatible shim.

Moved to ``app.agents.shared.middleware.skills_backends``. Re-exported here for
the frozen single-agent stack (``subagents/config``).
"""

from app.agents.shared.middleware.skills_backends import (
    SKILLS_BUILTIN_PREFIX,
    SKILLS_SPACE_PREFIX,
    BuiltinSkillsBackend,
    SearchSpaceSkillsBackend,
    build_skills_backend_factory,
    default_skills_sources,
)

__all__ = [
    "SKILLS_BUILTIN_PREFIX",
    "SKILLS_SPACE_PREFIX",
    "BuiltinSkillsBackend",
    "SearchSpaceSkillsBackend",
    "build_skills_backend_factory",
    "default_skills_sources",
]
