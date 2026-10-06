"""Whether the agent's model reads images, so opencode shows it the pages it opens.

The chat's own answer (ADR 0034), with no developer switch: an image a text-only
model refuses fails the request, and opencode re-sends it with every later one,
so a model the catalog does not know, or disagrees on, is shown none.
"""

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.model_window import selected_text_model
from modules.llm.catalog.remote.reads_images import remote_reads_images
from modules.llm.providers import get_provider, llamacpp


async def selected_model_reads_images(session: Session) -> bool:
    """llama-server's `/models` for a local model, the remote catalog for a remote one."""
    selected, catalog_provider = await transact(session, selected_text_model)
    if selected.provider == llamacpp.PROVIDER:
        return await _local_reads_images(selected.name)
    return remote_reads_images(selected.name, catalog_provider)


async def _local_reads_images(name: str) -> bool:
    """No answer is no: an image the model refuses fails the whole request."""
    provider = get_provider(llamacpp.PROVIDER)
    if not isinstance(provider, llamacpp.LlamaCppProvider):
        return False  # pragma: no cover - fixed registry invariant
    return bool(await provider.sees_images(name))
