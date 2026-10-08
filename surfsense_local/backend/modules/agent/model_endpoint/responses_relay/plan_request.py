"""A step opencode sends, kept within what a ChatGPT plan's Responses endpoint takes."""

from typing import Any

from modules.llm.providers.openai_responses.plan_limits import REFUSED_FIELDS

# The plan takes function tools only grouped in a namespace; one holds all of opencode's.
NAMESPACE = "surfsense"
_NAMESPACE_DESCRIPTION = "SurfSense's tools for working on the user's sources."


def within_plan(body: dict[str, Any]) -> dict[str, Any]:
    """Refused fields dropped, the system turn as the developer's, tools in one namespace."""
    shaped = {k: v for k, v in body.items() if k not in REFUSED_FIELDS}
    shaped["store"] = False
    shaped["stream"] = True
    shaped["input"] = [_item(item) for item in body.get("input") or []]
    tools = body.get("tools") or []
    functions = [tool for tool in tools if tool.get("type") == "function"]
    if functions:
        shaped["tools"] = [
            {
                "type": "namespace",
                "name": NAMESPACE,
                "description": _NAMESPACE_DESCRIPTION,
                "tools": functions,
            },
            *(tool for tool in tools if tool.get("type") != "function"),
        ]
    # How to name one function inside a namespace is not documented, so a call
    # forced by name becomes the model's own choice.
    if isinstance(shaped.get("tool_choice"), dict):
        shaped.pop("tool_choice")
    return shaped


def _item(item: dict[str, Any]) -> dict[str, Any]:
    """A plan rejects `system` items; an earlier call is replayed in the namespace it ran in."""
    if item.get("role") == "system":
        return {**item, "role": "developer"}
    if item.get("type") == "function_call" and not item.get("namespace"):
        return {**item, "namespace": NAMESPACE}
    return item
