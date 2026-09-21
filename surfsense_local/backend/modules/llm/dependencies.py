from typing import Annotated

from fastapi import Depends, HTTPException, status

from modules.llm.providers import get_provider, llamacpp
from modules.llm.providers.protocols import Generator


def get_provider_or_404(provider: str) -> Generator:
    """Resolve the provider in the path, or fail before the handler."""
    found = get_provider(provider)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider}")
    return found


ProviderDep = Annotated[Generator, Depends(get_provider_or_404)]


def get_local_runtime() -> Generator:
    """The one runtime that holds models on this machine.

    Routes that manage local files no longer name a provider in their path:
    there is exactly one, and asking the caller to spell it invites a request
    that names a remote endpoint and gets a confusing error instead of a route
    that could never have applied.
    """
    found = get_provider(llamacpp.PROVIDER)
    if found is None:  # pragma: no cover - fixed registry invariant
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "the local runtime is unavailable"
        )
    return found


LocalRuntimeDep = Annotated[Generator, Depends(get_local_runtime)]
