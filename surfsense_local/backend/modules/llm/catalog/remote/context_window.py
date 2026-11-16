"""The window the remote catalog records for a model, from the manifest alone."""

from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM

__all__ = ["remote_context_window"]


def remote_context_window(model_id: str, catalog_provider: str | None) -> int | None:
    """None for an id the manifest does not carry: unknown, not narrow."""
    provider = None if catalog_provider in (None, CUSTOM) else catalog_provider
    found = remote_lookup().classify(model_id, provider=provider)
    return found.supports.context_window if found.supports else None
