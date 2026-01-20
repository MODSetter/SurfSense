import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.db import SearchSourceConnectorType
from app.utils.validators import validate_connector_config

from .base import IDModel, TimestampModel


class SearchSourceConnectorBase(BaseModel):
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None = None
    config: dict[str, Any]
    periodic_indexing_enabled: bool = False
    indexing_frequency_minutes: int | None = None
    next_scheduled_at: datetime | None = None

    @field_validator("config")
    @classmethod
    def validate_config_for_connector_type(
        cls,
        config: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        connector_type = values.data.get("connector_type")
        return validate_connector_config(connector_type, config)

    @model_validator(mode="after")
    def validate_periodic_indexing(self):
        """Validate that periodic indexing configuration is consistent.

        Supported frequencies: Any positive integer (in minutes).
        Common values: 5, 15, 60 (1 hour), 360 (6 hours), 720 (12 hours), 1440 (daily), etc.
        The schedule checker will handle any frequency >= 1 minute.
        """
        if self.periodic_indexing_enabled:
            if not self.is_indexable:
                msg = "periodic_indexing_enabled can only be True for indexable connectors"
                raise ValueError(
                    msg,
                )
            if self.indexing_frequency_minutes is None:
                msg = "indexing_frequency_minutes is required when periodic_indexing_enabled is True"
                raise ValueError(
                    msg,
                )
            if self.indexing_frequency_minutes <= 0:
                msg = "indexing_frequency_minutes must be greater than 0"
                raise ValueError(msg)
        return self


class SearchSourceConnectorCreate(SearchSourceConnectorBase):
    pass


class SearchSourceConnectorUpdate(BaseModel):
    name: str | None = None
    connector_type: SearchSourceConnectorType | None = None
    is_indexable: bool | None = None
    last_indexed_at: datetime | None = None
    config: dict[str, Any] | None = None
    periodic_indexing_enabled: bool | None = None
    indexing_frequency_minutes: int | None = None
    next_scheduled_at: datetime | None = None


class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    search_space_id: int
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# MCP-specific schemas
# =============================================================================


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection.

    Supports two transport types:
    - stdio: Local process (command, args, env)
    - streamable-http/http/sse: Remote HTTP server (url, headers)
    """

    # stdio transport fields
    command: str | None = None  # e.g., "uvx", "node", "python"
    args: list[str] = []  # e.g., ["mcp-server-git", "--repository", "/path"]
    env: dict[str, str] = {}  # Environment variables for the server process

    # HTTP transport fields
    url: str | None = None  # e.g., "https://mcp-server.com/mcp"
    headers: dict[str, str] = {}  # HTTP headers for authentication

    transport: str = "stdio"  # "stdio" | "streamable-http" | "http" | "sse"

    def is_http_transport(self) -> bool:
        """Check if this config uses HTTP transport."""
        return self.transport in ("streamable-http", "http", "sse")


class MCPConnectorCreate(BaseModel):
    """Schema for creating an MCP connector."""

    name: str
    server_config: MCPServerConfig  # Single MCP server configuration


class MCPConnectorUpdate(BaseModel):
    """Schema for updating an MCP connector."""

    name: str | None = None
    server_config: MCPServerConfig | None = None


class MCPConnectorRead(BaseModel):
    """Schema for reading an MCP connector with server configs."""

    id: int
    name: str
    connector_type: SearchSourceConnectorType
    server_config: MCPServerConfig
    search_space_id: int
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_connector(cls, connector: SearchSourceConnectorRead) -> "MCPConnectorRead":
        """Convert from base SearchSourceConnectorRead."""
        config = connector.config or {}
        server_config_data = config.get("server_config", {})
        server_config = MCPServerConfig(**server_config_data)

        return cls(
            id=connector.id,
            name=connector.name,
            connector_type=connector.connector_type,
            server_config=server_config,
            search_space_id=connector.search_space_id,
            user_id=connector.user_id,
            created_at=connector.created_at,
            updated_at=connector.updated_at,
        )
