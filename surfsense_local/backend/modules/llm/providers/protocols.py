from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from modules.llm.providers.types import CatalogEntry, DownloadProgress, Message, Model


class Generator(Protocol):
    """Anything that can answer. Ollama today, other backends later."""

    name: str

    async def health(self) -> bool: ...

    async def models(self) -> list[Model]: ...

    def chat(self, model: str, messages: list[Message]) -> AsyncIterator[str]: ...


@runtime_checkable
class ModelStore(Protocol):
    """Only runtimes that keep models on disk can fetch them.

    Checked with isinstance, so a remote API that cannot download simply does
    not satisfy it and the download UI is hidden without naming a provider.
    """

    def catalog(self) -> list[CatalogEntry]: ...

    def pull(self, name: str) -> AsyncIterator[DownloadProgress]: ...
