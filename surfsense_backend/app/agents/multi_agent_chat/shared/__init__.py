"""Cross-cutting helpers: prompt loading, domain agent factory, connector deps."""

from app.agents.multi_agent_chat.shared.deps import connector_binding
from app.agents.multi_agent_chat.shared.domain_agent_factory import build_domain_agent
from app.agents.multi_agent_chat.shared.invoke_output import extract_last_assistant_text
from app.agents.multi_agent_chat.shared.prompt_loader import read_prompt_md

__all__ = [
    "build_domain_agent",
    "connector_binding",
    "extract_last_assistant_text",
    "read_prompt_md",
]
