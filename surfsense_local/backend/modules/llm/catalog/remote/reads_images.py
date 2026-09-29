"""Whether a remote model reads images, from the manifest alone.

The connection's model list, the selection and the send check all ask this one
function, so none of them can offer images another refuses.
"""

from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM

__all__ = ["remote_reads_images"]


def remote_reads_images(model_id: str, catalog_provider: str | None) -> bool:
    """True only when the manifest says so; an id it does not carry answers no."""
    provider = None if catalog_provider in (None, CUSTOM) else catalog_provider
    found = remote_lookup().classify(model_id, provider=provider)
    return bool(found.supports and found.supports.reads_images)
