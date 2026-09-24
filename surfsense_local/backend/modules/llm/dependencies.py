from typing import Annotated

from fastapi import Depends, HTTPException, status

from modules.llm.providers import get_provider
from modules.llm.providers.protocols import Generator


def get_provider_or_404(provider: str) -> Generator:
    """Resolve the provider in the path, or fail before the handler."""
    found = get_provider(provider)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider}")
    return found


ProviderDep = Annotated[Generator, Depends(get_provider_or_404)]
