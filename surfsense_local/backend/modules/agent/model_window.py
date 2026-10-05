"""The window the selected text model has, which opencode's limits are set from."""

import logging

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers import get_provider, llamacpp
from modules.llm.resolution import ModelResolutionError

logger = logging.getLogger(__name__)

# What an endpoint that reports no window is taken to have: the smallest window
# a model may run the agent at, so opencode compacts early rather than overflows.
FALLBACK_WINDOW = 32_768


async def selected_model_window(session: Session) -> tuple[str, int]:
    """The selected model's name and the window it answers within.

    A local model's is the window llama-server loaded it with; a remote one's is
    what the remote catalog records for it.
    """
    selected, catalog_provider = await transact(session, selected_text_model)
    if selected.provider == llamacpp.PROVIDER:
        window = await _local_window(selected.name)
    else:
        window = _catalog_window(selected.name, catalog_provider)
    return selected.name, window or FALLBACK_WINDOW


def selected_text_model(session: Session) -> tuple[SelectedModel, str | None]:
    """The selected text model, and the catalog provider its connection names."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise ModelResolutionError("no chat model selected")
    connection = (
        session.get(ProviderConnection, selected.connection_id)
        if selected.connection_id
        else None
    )
    return selected, connection.catalog_provider if connection else None


async def _local_window(name: str) -> int | None:
    """What llama-server allocated for the model, loading it if it is not resident."""
    provider = get_provider(llamacpp.PROVIDER)
    if provider is None:  # pragma: no cover - fixed registry invariant
        return None
    try:
        return await provider.context_tokens(name)
    except Exception:
        logger.warning("could not read the window of %s", name, exc_info=True)
        return None


def _catalog_window(name: str, catalog_provider: str | None) -> int | None:
    """The window the remote catalog records for the model, if it knows the model."""
    provider = None if catalog_provider in (None, CUSTOM) else catalog_provider
    found = remote_lookup().classify(name, provider=provider)
    return found.supports.context_window if found.supports else None
