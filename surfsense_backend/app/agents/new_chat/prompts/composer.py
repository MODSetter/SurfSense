"""
Prompt composer for the SurfSense ``new_chat`` agent.

This module assembles the agent's system prompt from the markdown fragments
under :mod:`app.agents.new_chat.prompts`. It replaces the monolithic
``system_prompt.py`` with a clean, fragment-based composition:

::

    prompts/
      base/                  # agent identity, KB policy, tool routing, …
      providers/             # provider-specific tweaks (anthropic, gpt5, …)
      tools/                 # one ``<name>.md`` per tool
      examples/              # one ``<name>.md`` per tool with call examples
      routing/               # connector-specific routing notes (linear, slack, …)

Tier 3a in the OpenCode-port plan.

Backwards compatibility
=======================

``system_prompt.py`` re-exports :func:`compose_system_prompt` and wraps it
in functions with the same signatures as the legacy
``build_surfsense_system_prompt`` / ``build_configurable_system_prompt`` so
existing call sites do not change.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from importlib import resources

from app.db import ChatVisibility

# -----------------------------------------------------------------------------
# Provider variant detection
# -----------------------------------------------------------------------------

ProviderVariant = str  # "anthropic" | "openai_reasoning" | "openai_classic" | "google" | "default"

_OPENAI_REASONING_RE = re.compile(r"\b(gpt-5|o\d|o-)", re.IGNORECASE)
_OPENAI_CLASSIC_RE = re.compile(r"\bgpt-4", re.IGNORECASE)
_ANTHROPIC_RE = re.compile(r"\bclaude\b", re.IGNORECASE)
_GOOGLE_RE = re.compile(r"\bgemini\b", re.IGNORECASE)


def detect_provider_variant(model_name: str | None) -> ProviderVariant:
    """Pick a provider-specific prompt variant from a model id string.

    Heuristic match on the model id; returns ``"default"`` when nothing
    matches so the composer can fall back to the empty placeholder file.
    """
    if not model_name:
        return "default"
    name = model_name.strip()
    if _OPENAI_REASONING_RE.search(name):
        return "openai_reasoning"
    if _OPENAI_CLASSIC_RE.search(name):
        return "openai_classic"
    if _ANTHROPIC_RE.search(name):
        return "anthropic"
    if _GOOGLE_RE.search(name):
        return "google"
    return "default"


# -----------------------------------------------------------------------------
# Fragment loading
# -----------------------------------------------------------------------------


_PROMPTS_PACKAGE = "app.agents.new_chat.prompts"


def _read_fragment(subpath: str) -> str:
    """Read a fragment file from the ``prompts/`` resource tree.

    Returns the raw contents stripped of any single trailing newline so
    composition can append explicit separators without compounding blank
    lines. Missing files return an empty string so optional fragments
    (e.g. provider hints) act as no-ops.
    """
    parts = subpath.split("/")
    try:
        ref = resources.files(_PROMPTS_PACKAGE).joinpath(*parts)
        if not ref.is_file():
            return ""
        text = ref.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return ""
    if text.endswith("\n"):
        text = text[:-1]
    return text


# -----------------------------------------------------------------------------
# Tool ordering + memory variant resolution
# -----------------------------------------------------------------------------


# Ordered for reading flow: fundamentals first, then artifact generators,
# then memory at the end (mirrors the legacy ``_ALL_TOOL_NAMES_ORDERED``).
ALL_TOOL_NAMES_ORDERED: tuple[str, ...] = (
    "search_surfsense_docs",
    "web_search",
    "generate_podcast",
    "generate_video_presentation",
    "generate_report",
    "generate_resume",
    "generate_image",
    "scrape_webpage",
    "update_memory",
)


_MEMORY_VARIANT_TOOLS: frozenset[str] = frozenset({"update_memory"})


def _tool_fragment_path(tool_name: str, variant: str) -> str:
    """Resolve a tool's instruction fragment path.

    Tools listed in :data:`_MEMORY_VARIANT_TOOLS` switch on the conversation
    visibility and load ``tools/<name>_<variant>.md``; everything else
    falls back to ``tools/<name>.md``.
    """
    if tool_name in _MEMORY_VARIANT_TOOLS:
        return f"tools/{tool_name}_{variant}.md"
    return f"tools/{tool_name}.md"


def _example_fragment_path(tool_name: str, variant: str) -> str:
    if tool_name in _MEMORY_VARIANT_TOOLS:
        return f"examples/{tool_name}_{variant}.md"
    return f"examples/{tool_name}.md"


def _format_tool_label(tool_name: str) -> str:
    return tool_name.replace("_", " ").title()


# -----------------------------------------------------------------------------
# Section builders
# -----------------------------------------------------------------------------


def _build_system_instructions(
    *,
    visibility: ChatVisibility,
    resolved_today: str,
) -> str:
    """Reconstruct the legacy ``<system_instruction>`` block from fragments."""
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"

    sections = [
        _read_fragment(f"base/agent_{variant}.md"),
        _read_fragment(f"base/kb_only_policy_{variant}.md"),
        _read_fragment(f"base/tool_routing_{variant}.md"),
        _read_fragment("base/parameter_resolution.md"),
        _read_fragment(f"base/memory_protocol_{variant}.md"),
    ]
    body = "\n\n".join(s for s in sections if s)
    block = f"\n<system_instruction>\n{body}\n\n</system_instruction>\n"
    return block.format(resolved_today=resolved_today)


def _build_mcp_routing_block(
    mcp_connector_tools: dict[str, list[str]] | None,
) -> str:
    """Emit the ``<mcp_tool_routing>`` block when at least one MCP server is wired."""
    if not mcp_connector_tools:
        return ""
    lines: list[str] = [
        "\n<mcp_tool_routing>",
        "You also have direct tools from these user-connected MCP servers.",
        "Their data is NEVER in the knowledge base — call their tools directly.",
        "",
    ]
    for server_name, tool_names in mcp_connector_tools.items():
        lines.append(f"- {server_name} → {', '.join(tool_names)}")
    lines.append("</mcp_tool_routing>\n")
    return "\n".join(lines)


def _build_tools_section(
    *,
    visibility: ChatVisibility,
    enabled_tool_names: set[str] | None,
    disabled_tool_names: set[str] | None,
) -> str:
    """Reconstruct the ``<tools>`` block + ``<tool_call_examples>`` block."""
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"

    parts: list[str] = []
    preamble = _read_fragment("tools/_preamble.md")
    if preamble:
        parts.append(preamble + "\n")

    examples: list[str] = []

    for tool_name in ALL_TOOL_NAMES_ORDERED:
        if enabled_tool_names is not None and tool_name not in enabled_tool_names:
            continue

        instruction = _read_fragment(_tool_fragment_path(tool_name, variant))
        if instruction:
            parts.append(instruction + "\n")

        example = _read_fragment(_example_fragment_path(tool_name, variant))
        if example:
            examples.append(example + "\n")

    known_disabled = (
        set(disabled_tool_names) & set(ALL_TOOL_NAMES_ORDERED)
        if disabled_tool_names
        else set()
    )
    if known_disabled:
        disabled_list = ", ".join(
            _format_tool_label(n)
            for n in ALL_TOOL_NAMES_ORDERED
            if n in known_disabled
        )
        parts.append(
            "\n"
            "DISABLED TOOLS (by user):\n"
            f"The following tools are available in SurfSense but have been disabled by the user for this session: {disabled_list}.\n"
            "You do NOT have access to these tools and MUST NOT claim you can use them.\n"
            "If the user asks about a capability provided by a disabled tool, let them know the relevant tool\n"
            "is currently disabled and they can re-enable it.\n"
        )

    parts.append("\n</tools>\n")

    if examples:
        parts.append("<tool_call_examples>")
        parts.extend(examples)
        parts.append("</tool_call_examples>\n")

    return "".join(parts)


def _build_provider_block(provider_variant: ProviderVariant) -> str:
    """Optional provider-tuned hints. Empty for ``"default"``."""
    if not provider_variant or provider_variant == "default":
        return ""
    text = _read_fragment(f"providers/{provider_variant}.md")
    return f"\n{text}\n" if text else ""


def _build_routing_block(connector_routing: Iterable[str] | None) -> str:
    if not connector_routing:
        return ""
    fragments: list[str] = []
    for name in connector_routing:
        text = _read_fragment(f"routing/{name}.md")
        if text:
            fragments.append(text)
    if not fragments:
        return ""
    return "\n" + "\n\n".join(fragments) + "\n"


def _build_citation_block(citations_enabled: bool) -> str:
    fragment = (
        _read_fragment("base/citations_on.md")
        if citations_enabled
        else _read_fragment("base/citations_off.md")
    )
    return f"\n{fragment}\n" if fragment else ""


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def compose_system_prompt(
    *,
    today: datetime | None = None,
    thread_visibility: ChatVisibility | None = None,
    enabled_tool_names: set[str] | None = None,
    disabled_tool_names: set[str] | None = None,
    mcp_connector_tools: dict[str, list[str]] | None = None,
    custom_system_instructions: str | None = None,
    use_default_system_instructions: bool = True,
    citations_enabled: bool = True,
    provider_variant: ProviderVariant | None = None,
    model_name: str | None = None,
    connector_routing: Iterable[str] | None = None,
) -> str:
    """Assemble the SurfSense system prompt from disk fragments.

    Args:
        today: Optional clock injection for tests.
        thread_visibility: Private vs shared (team) — drives memory wording
            and a few base block variants.
        enabled_tool_names: When provided, only these tools' instructions
            are included; ``None`` keeps the legacy "include everything"
            behavior.
        disabled_tool_names: User-disabled tools (note appended to prompt).
        mcp_connector_tools: ``{server_name: [tool_names...]}`` to inject
            an explicit MCP routing block.
        custom_system_instructions: Free-form instructions that override
            the default ``<system_instruction>`` block (legacy support
            for ``NewLLMConfig.system_instructions``).
        use_default_system_instructions: When ``custom_system_instructions``
            is empty/None, fall back to defaults (legacy semantics).
        citations_enabled: Include ``citations_on.md`` (true) or
            ``citations_off.md`` (false).
        provider_variant: Explicit provider variant override
            (``"anthropic" | "openai_reasoning" | "openai_classic" | "google" | "default"``).
            When ``None``, falls back to :func:`detect_provider_variant`
            on ``model_name``.
        model_name: Used to auto-detect ``provider_variant`` when not
            provided explicitly.
        connector_routing: Optional list of routing fragment names
            (``["linear", "slack", ...]``) to include from
            ``prompts/routing/``.

    Returns:
        The fully composed system prompt string.
    """
    resolved_today = (today or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    visibility = thread_visibility or ChatVisibility.PRIVATE

    if custom_system_instructions and custom_system_instructions.strip():
        sys_block = custom_system_instructions.format(resolved_today=resolved_today)
    elif use_default_system_instructions:
        sys_block = _build_system_instructions(
            visibility=visibility, resolved_today=resolved_today
        )
    else:
        sys_block = ""

    sys_block += _build_mcp_routing_block(mcp_connector_tools)

    if provider_variant is None:
        provider_variant = detect_provider_variant(model_name)
    sys_block += _build_provider_block(provider_variant)
    sys_block += _build_routing_block(connector_routing)

    tools_block = _build_tools_section(
        visibility=visibility,
        enabled_tool_names=enabled_tool_names,
        disabled_tool_names=disabled_tool_names,
    )
    citation_block = _build_citation_block(citations_enabled)

    return sys_block + tools_block + citation_block


__all__ = [
    "ALL_TOOL_NAMES_ORDERED",
    "ProviderVariant",
    "compose_system_prompt",
    "detect_provider_variant",
]
