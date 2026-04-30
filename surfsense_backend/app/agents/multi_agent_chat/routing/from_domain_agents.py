"""LangChain ``@tool`` wrappers that invoke compiled domain-agent graphs (supervisor-facing only)."""

from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Any

from langchain_core.tools import BaseTool, tool

from app.agents.multi_agent_chat.core.delegation import compose_child_task
from app.agents.multi_agent_chat.core.invocation import extract_last_assistant_text
from app.agents.multi_agent_chat.routing.domain_routing_spec import DomainRoutingSpec

_ALLOWED_STATUSES = {"success", "partial", "blocked", "error"}
_REQUIRED_KEYS = {
    "status",
    "action_summary",
    "evidence",
    "next_step",
    "missing_fields",
    "assumptions",
}


def _fallback_payload(spec: DomainRoutingSpec, reason: str, raw_text: str) -> dict[str, Any]:
    preview = raw_text[:800]
    return {
        "status": "error",
        "action_summary": "Domain agent output failed JSON contract validation.",
        "evidence": {
            "route_tool": spec.tool_name,
            "validation_error": reason,
            "raw_output_preview": preview,
        },
        "next_step": (
            "Re-delegate with a strict reminder to return exactly one JSON object "
            "matching the output_contract."
        ),
        "missing_fields": None,
        "assumptions": None,
    }


def _validate_contract_payload(payload: dict[str, Any]) -> str | None:
    missing = sorted(_REQUIRED_KEYS - set(payload))
    if missing:
        return f"missing required keys: {', '.join(missing)}"

    status = payload.get("status")
    if status not in _ALLOWED_STATUSES:
        return "invalid status value"

    action_summary = payload.get("action_summary")
    if not isinstance(action_summary, str) or not action_summary.strip():
        return "action_summary must be a non-empty string"

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return "evidence must be an object"

    next_step = payload.get("next_step")
    if status == "success":
        if next_step is not None:
            return "next_step must be null when status=success"
        if payload.get("missing_fields") is not None:
            return "missing_fields must be null when status=success"
    else:
        if not isinstance(next_step, str) or not next_step.strip():
            return "next_step must be a non-empty string for non-success statuses"

    missing_fields = payload.get("missing_fields")
    if missing_fields is not None:
        if not isinstance(missing_fields, list) or any(
            not isinstance(item, str) or not item.strip() for item in missing_fields
        ):
            return "missing_fields must be null or a list of non-empty strings"

    assumptions = payload.get("assumptions")
    if assumptions is not None:
        if not isinstance(assumptions, list) or any(
            not isinstance(item, str) or not item.strip() for item in assumptions
        ):
            return "assumptions must be null or a list of non-empty strings"

    return None


def _normalize_domain_output(spec: DomainRoutingSpec, raw_text: str) -> str:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        fallback = _fallback_payload(spec, f"invalid JSON: {exc.msg}", raw_text)
        return json.dumps(fallback)

    if not isinstance(parsed, dict):
        fallback = _fallback_payload(spec, "top-level JSON must be an object", raw_text)
        return json.dumps(fallback)

    validation_error = _validate_contract_payload(parsed)
    if validation_error:
        fallback = _fallback_payload(spec, validation_error, raw_text)
        return json.dumps(fallback)

    return json.dumps(parsed)


def _routing_tool_for_spec(spec: DomainRoutingSpec) -> BaseTool:
    @tool(spec.tool_name, description=spec.description)
    async def _route(task: str) -> str:
        curated = spec.curated_context(task) if spec.curated_context else None
        content = compose_child_task(task, curated_context=curated)
        result = await spec.domain_agent.ainvoke(
            {"messages": [{"role": "user", "content": content}]},
        )
        return _normalize_domain_output(spec, extract_last_assistant_text(result))

    return _route


def routing_tools_from_specs(specs: Sequence[DomainRoutingSpec]) -> list[BaseTool]:
    """Build one supervisor-facing routing ``@tool`` per :class:`DomainRoutingSpec`."""
    return [_routing_tool_for_spec(spec) for spec in specs]
