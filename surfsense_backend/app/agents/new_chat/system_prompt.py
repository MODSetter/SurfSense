"""Backward-compatible shim.

Moved to ``app.agents.shared.system_prompt``. Re-exported here for the frozen
single-agent stack (``chat_deepagent``) until that stack is retired.
"""

from app.agents.shared.system_prompt import (
    SURFSENSE_CITATION_INSTRUCTIONS,
    SURFSENSE_NO_CITATION_INSTRUCTIONS,
    SURFSENSE_SYSTEM_INSTRUCTIONS_TEMPLATE,
    SURFSENSE_SYSTEM_PROMPT,
    build_configurable_system_prompt,
    build_surfsense_system_prompt,
    compose_system_prompt,
    detect_provider_variant,
    get_default_system_instructions,
)

__all__ = [
    "SURFSENSE_CITATION_INSTRUCTIONS",
    "SURFSENSE_NO_CITATION_INSTRUCTIONS",
    "SURFSENSE_SYSTEM_INSTRUCTIONS_TEMPLATE",
    "SURFSENSE_SYSTEM_PROMPT",
    "build_configurable_system_prompt",
    "build_surfsense_system_prompt",
    "compose_system_prompt",
    "detect_provider_variant",
    "get_default_system_instructions",
]
