"""Backward-compatible shim.

Moved to ``app.agents.shared.agent_cache``. Re-exported here for the frozen
single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.agent_cache import (
    flags_signature,
    get_cache,
    reload_for_tests,
    stable_hash,
    system_prompt_hash,
    tools_signature,
)

__all__ = [
    "flags_signature",
    "get_cache",
    "reload_for_tests",
    "stable_hash",
    "system_prompt_hash",
    "tools_signature",
]
