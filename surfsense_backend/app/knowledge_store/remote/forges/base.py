"""How a forge authenticates and accepts a remote."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.knowledge_store.remote.schemas import RemoteCredentials, RemoteSpec


class RemoteProvider(ABC):
    """Forge-specific validate + credentials. Add/remove/list stay on WorkspaceRemotes."""

    @abstractmethod
    def validate(self, spec: RemoteSpec) -> None:
        """Raise ``RemoteError`` if ``spec`` is not acceptable for this forge."""

    @abstractmethod
    async def credentials(self, spec: RemoteSpec) -> RemoteCredentials:
        """HTTPS username/password for ``list_remote_branches`` / ``push``."""
