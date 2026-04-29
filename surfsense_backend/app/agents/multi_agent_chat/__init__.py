"""
Multi-agent chat (LangChain Subagents pattern).

**Vertical slices**

- :mod:`gmail` — connector tools, domain agent, ``domain_prompt.md``
- :mod:`calendar` — connector tools, domain agent, ``domain_prompt.md``

**Shared**

- :mod:`shared` — prompt loader, ``build_domain_agent``, connector deps, invoke result parsing

**Cross-cutting**

- :mod:`routing` — supervisor routing tools + invoke helpers
- :mod:`supervisor` — top graph + ``supervisor_prompt.md``
- :mod:`integration` — ``create_multi_agent_chat``

Documentation:
https://docs.langchain.com/oss/python/langchain/multi-agent
https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

Display name: ``multi-agent-chat`` — Python package: ``multi_agent_chat``.
"""

from app.agents.multi_agent_chat.calendar import (
    build_calendar_domain_agent,
    build_google_calendar_connector_tools,
)
from app.agents.multi_agent_chat.gmail import (
    build_gmail_connector_tools,
    build_gmail_domain_agent,
)
from app.agents.multi_agent_chat.integration import create_multi_agent_chat
from app.agents.multi_agent_chat.shared import (
    build_domain_agent,
    connector_binding,
    extract_last_assistant_text,
    read_prompt_md,
)
from app.agents.multi_agent_chat.routing import (
    build_supervisor_routing_tools,
    routing_tools_from_domain_agents,
)
from app.agents.multi_agent_chat.supervisor import build_supervisor_agent

__all__ = [
    "build_calendar_domain_agent",
    "build_domain_agent",
    "build_gmail_connector_tools",
    "build_gmail_domain_agent",
    "build_google_calendar_connector_tools",
    "build_supervisor_agent",
    "build_supervisor_routing_tools",
    "connector_binding",
    "create_multi_agent_chat",
    "extract_last_assistant_text",
    "read_prompt_md",
    "routing_tools_from_domain_agents",
]
