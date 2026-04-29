"""Supervisor-scoped system prompt for ``new_chat_supervisor_baseline``.

Composition follows the same fragment discipline as
:func:`app.agents.new_chat.prompts.composer.compose_system_prompt`, but **omits**
sections that assume registry tools: ``base/tool_routing_*.md``, ``tools/_preamble.md``,
the tools/examples blocks, ``base/parameter_resolution.md`` (discovery lists concrete
tools), and ``base/memory_protocol_*.md`` (requires ``update_memory`` calls).

**Authoritative supervisor semantics:** LangChain Reference documents
``langgraph_supervisor.create_supervisor`` — the supervisor graph accepts an optional
``prompt`` (typically a ``SystemMessage``) that scopes the supervisor LLM alongside
managed worker graphs.

**SurfSense sources reused verbatim where applicable:** ``prompts/base/agent_private.md`` /
``agent_team.md`` from :mod:`app.agents.new_chat.prompts`. KB policy is adapted from
``base/kb_only_policy_*.md`` into supervisor-local fragments that reference injected
context instead of tool outputs. Provider and citation blocks reuse
``composer._build_provider_block`` / ``_build_citation_block`` and
``composer.detect_provider_variant`` unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import resources

from langchain_core.language_models import BaseChatModel

from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.prompts import composer as pc
from app.db import ChatVisibility

_SUP_PROMPTS_PKG = "app.agents.new_chat_supervisor_baseline.prompts"


def _read_supervisor_fragment(filename: str) -> str:
    try:
        ref = resources.files(_SUP_PROMPTS_PKG).joinpath(filename)
        if not ref.is_file():
            return ""
        text = ref.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return ""
    if text.endswith("\n"):
        text = text[:-1]
    return text


def _build_supervisor_system_instruction_block(
    *,
    visibility: ChatVisibility,
    resolved_today: str,
) -> str:
    """``<system_instruction>`` body: LangGraph supervisor scope + SurfSense identity + adapted KB + memory limits."""
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"
    sections = [
        _read_supervisor_fragment("supervisor_graph_role.md"),
        pc._read_fragment(f"base/agent_{variant}.md"),
        _read_supervisor_fragment(f"kb_policy_supervisor_{variant}.md"),
        _read_supervisor_fragment("memory_context_supervisor.md"),
    ]
    body = "\n\n".join(s for s in sections if s)
    block = f"\n<system_instruction>\n{body}\n\n</system_instruction>\n"
    return block.format(resolved_today=resolved_today)


def resolve_llm_model_name(llm: BaseChatModel) -> str | None:
    """Best-effort model id string for :func:`composer.detect_provider_variant`."""
    name = getattr(llm, "model_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    model = getattr(llm, "model", None)
    if isinstance(model, str) and model.strip():
        return model.strip()
    profile = getattr(llm, "profile", None)
    if isinstance(profile, dict):
        for key in ("model", "model_name"):
            m = profile.get(key)
            if isinstance(m, str) and m.strip():
                return m.strip()
    return None


def build_supervisor_system_prompt(
    *,
    agent_config: AgentConfig | None,
    thread_visibility: ChatVisibility | None,
    llm: BaseChatModel,
) -> str:
    """Assemble the supervisor system prompt (no tool-list or tool-routing fragments)."""
    resolved_today = datetime.now(UTC).astimezone(UTC).date().isoformat()
    visibility = thread_visibility or ChatVisibility.PRIVATE
    model_name = resolve_llm_model_name(llm)

    if agent_config is not None:
        custom = (agent_config.system_instructions or "").strip()
        if custom:
            sys_block = agent_config.system_instructions.format(resolved_today=resolved_today)
        elif agent_config.use_default_system_instructions:
            sys_block = _build_supervisor_system_instruction_block(
                visibility=visibility,
                resolved_today=resolved_today,
            )
        else:
            sys_block = ""
    else:
        sys_block = _build_supervisor_system_instruction_block(
            visibility=visibility,
            resolved_today=resolved_today,
        )

    provider_variant = pc.detect_provider_variant(model_name)
    sys_block += pc._build_provider_block(provider_variant)

    if agent_config is None:
        citations_enabled = True
    else:
        citations_enabled = agent_config.citations_enabled

    sys_block += pc._build_citation_block(citations_enabled)
    return sys_block
