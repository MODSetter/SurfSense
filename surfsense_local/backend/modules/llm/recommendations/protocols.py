from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from modules.llm.providers.types import DownloadProgress
from modules.llm.recommendations.types import (
    AdvisorCatalog,
    InstalledModel,
    InstallPlan,
    ScoredModel,
)


class ModelAdvisor(Protocol):
    async def scan(self, max_context: int) -> AdvisorCatalog: ...


@runtime_checkable
class LocalRuntime(Protocol):
    name: str

    async def health(self) -> bool: ...

    async def resolve(self, model: ScoredModel) -> InstallPlan | None: ...

    async def installed_models(self) -> list[InstalledModel]: ...

    def install(self, plan: InstallPlan) -> AsyncIterator[DownloadProgress]: ...


@runtime_checkable
class CancelledDownloadCleaner(Protocol):
    async def cleanup_cancelled_download(self) -> None: ...
