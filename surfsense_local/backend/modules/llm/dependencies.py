from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.dependencies import SessionDep
from modules.llm.providers import get_provider
from modules.llm.providers.protocols import Generator, ModelStore


def get_provider_or_404(provider: str, session: SessionDep) -> Generator:
    """Resolve the provider in the path, or fail before the handler."""
    found = get_provider(provider, session)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider}")
    return found


ProviderDep = Annotated[Generator, Depends(get_provider_or_404)]


def get_store_or_409(provider: ProviderDep) -> ModelStore:
    """The provider as a store, or a 409: a remote API cannot download."""
    if not isinstance(provider, ModelStore):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{provider.name} cannot download models"
        )
    return provider


StoreDep = Annotated[ModelStore, Depends(get_store_or_409)]
