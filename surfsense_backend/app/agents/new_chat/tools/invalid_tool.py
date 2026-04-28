"""
The ``invalid`` fallback tool.

When the model emits a tool call whose name doesn't match any registered
tool, :class:`ToolCallNameRepairMiddleware` rewrites the call to ``invalid``
with the original name and a parser/validation error string. This tool's
execution then returns that error to the model so it can self-correct.

Mirrors ``opencode/packages/opencode/src/tool/invalid.ts``. Tier 1.6 in
the OpenCode-port plan.

Critically, the :class:`ToolDefinition` for this tool is **excluded** from
the system-prompt tool list and from ``LLMToolSelectorMiddleware`` selection
(see ``ToolDefinition.always_include`` filtering in the registry) — the
model never advertises ``invalid`` as a callable. It only ever shows up
in the tool registry so LangGraph can dispatch the rewritten call.
"""

from __future__ import annotations

from langchain_core.tools import tool

INVALID_TOOL_NAME = "invalid"
INVALID_TOOL_DESCRIPTION = "Do not use"


def _format_invalid_message(tool: str | None, error: str | None) -> str:
    """Return the user-visible error string. Mirrors ``invalid.ts``."""
    name = tool or "<unknown>"
    detail = error or "(no error message provided)"
    return (
        f"The arguments provided to the tool `{name}` are invalid: {detail}\n"
        f"Read the tool's docstring carefully and try again with valid arguments."
    )


@tool(name_or_callable=INVALID_TOOL_NAME, description=INVALID_TOOL_DESCRIPTION)
def invalid_tool(tool: str | None = None, error: str | None = None) -> str:
    """Return a human-readable explanation of a tool-call validation failure.

    Activated only when :class:`ToolCallNameRepairMiddleware` rewrites a
    failed tool call to ``invalid`` with the original tool name and the
    error message produced during validation.
    """
    return _format_invalid_message(tool, error)


__all__ = [
    "INVALID_TOOL_DESCRIPTION",
    "INVALID_TOOL_NAME",
    "invalid_tool",
]
