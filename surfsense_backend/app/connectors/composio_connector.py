"""
Composio Connector Base Module.

Provides a base class for interacting with various services via Composio,
primarily used during indexing operations.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSourceConnector
from app.services.composio_service import INDEXABLE_TOOLKITS, ComposioService

logger = logging.getLogger(__name__)


class ComposioConnector:
    """
    Base Composio connector for data retrieval.

    Wraps the ComposioService to provide toolkit-specific data access
    for indexing operations. Subclasses implement toolkit-specific methods.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
    ):
        """
        Initialize the Composio connector.

        Args:
            session: Database session for updating connector.
            connector_id: ID of the SearchSourceConnector.
        """
        self._session = session
        self._connector_id = connector_id
        self._service: ComposioService | None = None
        self._connector: SearchSourceConnector | None = None
        self._config: dict[str, Any] | None = None

    async def _load_connector(self) -> SearchSourceConnector:
        """Load connector from database."""
        if self._connector is None:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            self._connector = result.scalars().first()
            if not self._connector:
                raise ValueError(f"Connector {self._connector_id} not found")
            self._config = self._connector.config or {}
        return self._connector

    async def _get_service(self) -> ComposioService:
        """Get or create the Composio service instance."""
        if self._service is None:
            self._service = ComposioService()
        return self._service

    async def get_config(self) -> dict[str, Any]:
        """Get the connector configuration."""
        await self._load_connector()
        return self._config or {}

    async def get_toolkit_id(self) -> str:
        """Get the toolkit ID for this connector."""
        config = await self.get_config()
        return config.get("toolkit_id", "")

    async def get_connected_account_id(self) -> str | None:
        """Get the Composio connected account ID."""
        config = await self.get_config()
        return config.get("composio_connected_account_id")

    async def get_entity_id(self) -> str:
        """Get the Composio entity ID (user identifier)."""
        await self._load_connector()
        # Entity ID is constructed from the connector's user_id
        return f"surfsense_{self._connector.user_id}"

    async def is_indexable(self) -> bool:
        """Check if this connector's toolkit supports indexing."""
        toolkit_id = await self.get_toolkit_id()
        return toolkit_id in INDEXABLE_TOOLKITS

    @property
    def session(self) -> AsyncSession:
        """Get the database session."""
        return self._session

    @property
    def connector_id(self) -> int:
        """Get the connector ID."""
        return self._connector_id
