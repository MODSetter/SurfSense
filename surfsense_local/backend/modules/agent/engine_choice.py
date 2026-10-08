"""Which engine a new thread gets: the mode the user chose, or the selected model's default.

docs/architecture/agent.md, Which threads get it. A thread keeps what it got.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.llm.capability.agent_gate import (
    ToolFacts,
    catalog_facts,
    gate_block,
    local_facts,
    remote_facts,
)
from modules.llm.capability.modes import (
    ChatMode,
    NewChatModes,
    mode_entry,
    new_chat_modes,
    remember_mode,
)
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp
from shared.config import get_agent_settings

__all__ = [
    "AgenticRefusedError",
    "NewThreadMode",
    "new_thread_mode",
    "remember_thread_mode",
    "selected_model_can_run_agent",
]


# English for the API's own callers; the interface words each code itself.
_REFUSALS = {
    "no_model": "Choose a chat model first.",
    "agent_not_installed": "This install has no agent. Start a Basic (Q&A) chat.",
    "tool_calls_unsupported": "This model can't use tools, so it can't run Agentic mode.",
    "window_below_floor": (
        "This model's context window is under 32,768 tokens, too small for Agentic mode."
    ),
}


class AgenticRefusedError(Exception):
    """Agentic was asked for and a technical gate keeps the selected model out."""

    def __init__(self, code: str) -> None:
        super().__init__(_REFUSALS[code])
        # `no_model`, `agent_not_installed`, `tool_calls_unsupported` or `window_below_floor`.
        self.code = code


@dataclass(frozen=True)
class _Chosen:
    """The selected text model as the choice reads it, off the session."""

    name: str
    local_runtime: bool
    catalog_provider: str | None
    modes: NewChatModes
    entry: str


@dataclass(frozen=True)
class NewThreadMode:
    mode: ChatMode
    # The model it was decided on, as its remembered mode is kept; None with no model.
    # Read with the choice: the slot may hold another once the agent has started.
    entry: str | None


async def new_thread_mode(
    session: Session, requested: ChatMode | None
) -> NewThreadMode:
    """The mode a new thread opens in, and the model it was decided on.

    Asked for Agentic and refused, it raises; with nothing asked, as older
    clients send, the default falls back to Basic where Agentic cannot run.
    """
    chosen = await transact(session, _chosen)
    if chosen is None:
        if requested is ChatMode.AGENTIC:
            raise AgenticRefusedError("no_model")
        return NewThreadMode(ChatMode.BASIC, None)
    mode = requested or chosen.modes.default_mode
    if mode is ChatMode.BASIC:
        return NewThreadMode(mode, chosen.entry)
    blocked = chosen.modes.blocked
    if blocked is None and chosen.local_runtime:
        # Read only now: it loads the model, which a Basic chat may not need yet.
        blocked = _gate(await local_facts(chosen.name))
    if blocked is None:
        return NewThreadMode(ChatMode.AGENTIC, chosen.entry)
    if requested is ChatMode.AGENTIC:
        raise AgenticRefusedError(blocked)
    return NewThreadMode(ChatMode.BASIC, chosen.entry)


async def selected_model_can_run_agent(session: Session) -> bool:
    """Whether an agent thread's next turn may run on the selected model.

    The thread chose Agentic when it opened; only a technical gate stops a turn.
    """
    chosen = await transact(session, _chosen)
    if chosen is None or not get_agent_settings().has_opencode():
        return False
    facts = (
        await local_facts(chosen.name)
        if chosen.local_runtime
        else remote_facts(chosen.name, chosen.catalog_provider)
    )
    return _gate(facts) is None


async def remember_thread_mode(session: Session, entry: str, mode: ChatMode) -> None:
    """The mode the user chose for a new chat becomes that model's default for new ones.

    `entry` is `NewThreadMode.entry`, the model the chat's mode was decided on.
    """
    await transact(session, _remember, entry, mode)


def _gate(facts: ToolFacts) -> str | None:
    return gate_block(
        facts, window_floor=not get_agent_settings().agent_untested_models
    )


def _chosen(session: Session) -> _Chosen | None:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        return None
    connection = selected.connection
    catalog_provider = connection.catalog_provider if connection else None
    return _Chosen(
        name=selected.name,
        local_runtime=selected.provider == llamacpp.PROVIDER,
        catalog_provider=catalog_provider,
        modes=new_chat_modes(selected, catalog_facts(selected, catalog_provider)),
        entry=mode_entry(selected),
    )


def _remember(session: Session, entry: str, mode: ChatMode) -> None:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is not None:
        remember_mode(selected, mode, entry)
