"""Which engine a new thread gets: the agent for a tested model that can call tools, the chat for every other.

docs/proposals/agent/01-which-engine.md. A thread keeps what it got.
"""

import logging

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers import get_provider, llamacpp
from shared.config import get_agent_settings

logger = logging.getLogger(__name__)

# Models that passed the agent's test at a window of 32,768 tokens or more.
TESTED_MODELS: frozenset[str] = frozenset()


async def selected_model_can_run_agent(session: Session) -> bool:
    """Whether the selected text model may run the agent: tested, and known to call tools.

    Under the developer switch a remote model the catalog says nothing of is let in.
    """
    found = await transact(session, _selected)
    if found is None:
        return False
    selected, catalog_provider = found
    switch = get_agent_settings().agent_untested_models
    if not (selected.name in TESTED_MODELS or switch):
        return False
    if selected.provider == llamacpp.PROVIDER:
        return await _local_calls_tools(selected.name)
    stated = _catalog_tool_call(selected.name, catalog_provider)
    # The packaged catalog lags the providers; under the switch only a stated no keeps a model out.
    return stated is True or (stated is None and switch)


def _selected(session: Session) -> tuple[SelectedModel, str | None] | None:
    """The selected text model and the catalog provider its connection names, if any is selected."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        return None
    connection = (
        session.get(ProviderConnection, selected.connection_id)
        if selected.connection_id
        else None
    )
    return selected, connection.catalog_provider if connection else None


async def _local_calls_tools(name: str) -> bool:
    """Whether llama-server parses the model's tool calls, loading it if it is not resident."""
    provider = get_provider(llamacpp.PROVIDER)
    if not isinstance(provider, llamacpp.LlamaCppProvider):
        return False  # pragma: no cover - fixed registry invariant
    try:
        return (await provider.capabilities(name)).tool_calls
    except Exception:
        logger.warning("could not read whether %s calls tools", name, exc_info=True)
        return False


def _catalog_tool_call(name: str, catalog_provider: str | None) -> bool | None:
    """What the remote catalog says of the model's tool calls; None when it says nothing."""
    provider = None if catalog_provider in (None, CUSTOM) else catalog_provider
    found = remote_lookup().classify(name, provider=provider)
    return found.supports.tool_call if found.supports is not None else None
