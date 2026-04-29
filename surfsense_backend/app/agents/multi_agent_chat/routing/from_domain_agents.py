"""LangChain ``@tool`` wrappers that invoke compiled domain-agent graphs (supervisor-facing only)."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool

from app.agents.multi_agent_chat.shared.invoke_output import extract_last_assistant_text


def routing_tools_from_domain_agents(
    *,
    gmail_domain_agent: Any,
    calendar_domain_agent: Any,
) -> list[BaseTool]:
    """Build ``gmail`` / ``calendar`` tools that invoke the given graphs (factory, not import-time exports)."""

    @tool(
        "gmail",
        description=(
            "Route Gmail-related work to the Gmail sub-agent. "
            "Pass a clear natural-language task."
        ),
    )
    def call_gmail_agent(task: str) -> str:
        result = gmail_domain_agent.invoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        return extract_last_assistant_text(result)

    @tool(
        "calendar",
        description=(
            "Route Google Calendar work to the Calendar sub-agent. "
            "Pass a clear natural-language task."
        ),
    )
    def call_calendar_agent(task: str) -> str:
        result = calendar_domain_agent.invoke(
            {"messages": [{"role": "user", "content": task}]}
        )
        return extract_last_assistant_text(result)

    return [call_gmail_agent, call_calendar_agent]
