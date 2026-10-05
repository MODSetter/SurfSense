"""Which engine a new thread gets: the agent for a model measured to run it, or one the user opted in; the chat for every other.

docs/proposals/agent/01-which-engine.md. A thread keeps what it got.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.llm.capability import AGENT_LEVELS, Level, capability_of
from modules.llm.capability.agent_gate import gate_block, local_facts, remote_facts
from modules.llm.capability.agent_trial import agent_trial
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp
from shared.config import get_agent_settings


@dataclass(frozen=True)
class _Candidate:
    name: str
    local_runtime: bool
    catalog_provider: str | None
    # Measured at or near the bar, so its tool calls are shown, not stated.
    measured: bool
    # Measured, or not measured and opted in by the user.
    admitted: bool


async def selected_model_can_run_agent(session: Session) -> bool:
    """Whether the selected text model may run the agent.

    Measured at or near the bar, or not measured and opted in; then it must call
    tools and fit the agent's window. The developer switch lets every model in,
    and under it only a stated no on tool calls keeps one out.
    """
    candidate = await transact(session, _candidate)
    if candidate is None:
        return False
    switch = get_agent_settings().agent_untested_models
    if not (candidate.admitted or switch):
        return False
    facts = (
        await local_facts(candidate.name)
        if candidate.local_runtime
        else remote_facts(candidate.name, candidate.catalog_provider)
    )
    if switch:
        # The packaged catalog lags the providers; only a stated no keeps a model out.
        return facts.tool_calls is not False
    return gate_block(facts, measured=candidate.measured) is None


def _candidate(session: Session) -> _Candidate | None:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        return None
    connection = selected.connection
    level = capability_of(selected.name, connection).level
    measured = level in AGENT_LEVELS
    return _Candidate(
        name=selected.name,
        local_runtime=selected.provider == llamacpp.PROVIDER,
        catalog_provider=connection.catalog_provider if connection else None,
        measured=measured,
        admitted=measured or (level is Level.NOT_MEASURED and agent_trial(selected)),
    )
