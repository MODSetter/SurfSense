"""
Thin compatibility wrapper around :mod:`app.agents.new_chat.prompts.composer`.

The composer split the previous monolithic prompt string into a fragment
tree under ``prompts/`` plus a model-family dispatch step (see the
composer module docstring for credits). This module preserves the public
function surface (``build_surfsense_system_prompt`` /
``build_configurable_system_prompt`` /
``get_default_system_instructions`` / ``SURFSENSE_SYSTEM_PROMPT``) so
that existing call sites — `chat_deepagent.py`, anonymous chat routes,
and the configurable-prompt admin path — keep working without churn.

For new call sites prefer importing ``compose_system_prompt`` directly
from :mod:`app.agents.new_chat.prompts.composer`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.db import ChatVisibility

from .prompts.composer import (
    _read_fragment,
    compose_system_prompt,
    detect_provider_variant,
)

# Public re-exports for backwards compatibility (some legacy code reads the
# raw default-instructions text directly).
SURFSENSE_SYSTEM_INSTRUCTIONS_TEMPLATE = (
    "<system_instruction>\nDefault SurfSense agent system instructions are now\n"
    "composed from prompts/base/*.md. See compose_system_prompt() for details.\n"
    "</system_instruction>"
)

# Citation block re-exposed for legacy importers that referenced this constant
# directly. The composer is the canonical source; this is a frozen snapshot
# loaded at module-init time.
SURFSENSE_CITATION_INSTRUCTIONS = _read_fragment("base/citations_on.md")
SURFSENSE_NO_CITATION_INSTRUCTIONS = _read_fragment("base/citations_off.md")


def build_surfsense_system_prompt(
    today: datetime | None = None,
    thread_visibility: ChatVisibility | None = None,
    enabled_tool_names: set[str] | None = None,
    disabled_tool_names: set[str] | None = None,
    mcp_connector_tools: dict[str, list[str]] | None = None,
    *,
    model_name: str | None = None,
) -> str:
    """Build the default SurfSense system prompt (citations on, defaults).

    See :func:`app.agents.new_chat.prompts.composer.compose_system_prompt`
    for full parameter docs.
    """
    return compose_system_prompt(
        today=today,
        thread_visibility=thread_visibility,
        enabled_tool_names=enabled_tool_names,
        disabled_tool_names=disabled_tool_names,
        mcp_connector_tools=mcp_connector_tools,
        citations_enabled=True,
        model_name=model_name,
    )


def build_configurable_system_prompt(
    custom_system_instructions: str | None = None,
    use_default_system_instructions: bool = True,
    citations_enabled: bool = True,
    today: datetime | None = None,
    thread_visibility: ChatVisibility | None = None,
    enabled_tool_names: set[str] | None = None,
    disabled_tool_names: set[str] | None = None,
    mcp_connector_tools: dict[str, list[str]] | None = None,
    *,
    model_name: str | None = None,
) -> str:
    """Build a configurable SurfSense system prompt (NewLLMConfig path).

    See :func:`app.agents.new_chat.prompts.composer.compose_system_prompt`
    for full parameter docs.
    """
    return compose_system_prompt(
        today=today,
        thread_visibility=thread_visibility,
        enabled_tool_names=enabled_tool_names,
        disabled_tool_names=disabled_tool_names,
        mcp_connector_tools=mcp_connector_tools,
        custom_system_instructions=custom_system_instructions,
        use_default_system_instructions=use_default_system_instructions,
        citations_enabled=citations_enabled,
        model_name=model_name,
    )


def get_default_system_instructions() -> str:
    """Return the default ``<system_instruction>`` block (no tools / citations).

    Useful for populating the UI when seeding ``NewLLMConfig.system_instructions``.
    The output reflects the current fragment tree, not a baked-in constant.
    """
    resolved_today = datetime.now(UTC).date().isoformat()
    from .prompts.composer import _build_system_instructions  # local import

    return _build_system_instructions(
        visibility=ChatVisibility.PRIVATE,
        resolved_today=resolved_today,
    ).strip()


# Backwards compatibility — some modules import the constant directly.
SURFSENSE_SYSTEM_PROMPT = build_surfsense_system_prompt()


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
