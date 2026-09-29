"""Whether the selected model reads images, as the composer is told before a send."""

from sqlalchemy.orm import Session

from modules.llm.catalog.remote.reads_images import remote_reads_images
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers import get_provider, llamacpp

__all__ = ["connection_catalog_provider", "selection_reads_images"]


def connection_catalog_provider(
    session: Session, selected: SelectedModel
) -> str | None:
    """The manifest provider a remote selection is read through; None when local
    or when its connection is gone. Session work, so it runs apart from the ask."""
    if selected.connection_id is None:
        return None
    connection = session.get(ProviderConnection, selected.connection_id)
    return connection.catalog_provider if connection is not None else None


async def selection_reads_images(
    selected: SelectedModel, catalog_provider: str | None
) -> bool:
    """llama.cpp's `/models` for a local model, the manifest for a remote one.

    No answer is no here: offering attach to a model nothing vouches for is the
    silent failure the send check exists to catch, not to cause.
    """
    if selected.model_type is not ModelType.TEXT_GEN:
        return False
    if selected.provider == llamacpp.PROVIDER:
        provider = get_provider(llamacpp.PROVIDER)
        return bool(provider and await provider.sees_images(selected.name))
    return catalog_provider is not None and remote_reads_images(
        selected.name, catalog_provider
    )
