"""LangChain ``@tool`` wrappers that invoke compiled domain-agent graphs (supervisor-facing only)."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool, tool

from app.agents.multi_agent_chat.routing.domain_routing_spec import DomainRoutingSpec
from app.agents.multi_agent_chat.core.delegation import compose_child_task
from app.agents.multi_agent_chat.core.invocation import extract_last_assistant_text


def _routing_tool_for_spec(spec: DomainRoutingSpec) -> BaseTool:
    @tool(spec.tool_name, description=spec.description)
    def _route(task: str) -> str:
        curated = spec.curated_context(task) if spec.curated_context else None
        content = compose_child_task(task, curated_context=curated)
        result = spec.domain_agent.invoke(
            {"messages": [{"role": "user", "content": content}]},
        )
        return extract_last_assistant_text(result)

    return _route


def routing_tools_from_specs(specs: Sequence[DomainRoutingSpec]) -> list[BaseTool]:
    """Build one supervisor-facing routing ``@tool`` per :class:`DomainRoutingSpec`."""
    return [_routing_tool_for_spec(spec) for spec in specs]
