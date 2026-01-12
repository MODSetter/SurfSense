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
        cls, config: dict[str, Any], values: dict[str, Any],
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


class MCPToolConfig(BaseModel):
    """Configuration for a single MCP tool (API endpoint)."""

    name: str
    description: str
    endpoint: str
    method: str = "GET"
    auth_type: str = "none"  # "none" | "bearer" | "api_key" | "basic"
    auth_config: dict[str, Any] = {}
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        v_upper = v.upper()
        if v_upper not in allowed_methods:
            msg = f"Method must be one of {allowed_methods}"
            raise ValueError(msg)
        return v_upper

    @field_validator("auth_type")
    @classmethod
    def validate_auth_type(cls, v: str) -> str:
        allowed_types = ["none", "bearer", "api_key", "basic"]
        v_lower = v.lower()
        if v_lower not in allowed_types:
            msg = f"Auth type must be one of {allowed_types}"
            raise ValueError(msg)
        return v_lower


class MCPConnectorMetadata(BaseModel):
    """Metadata structure for MCP connectors."""

    tools: list[MCPToolConfig]


class MCPConnectorCreate(BaseModel):
    """Schema for creating an MCP connector."""

    name: str
    tools: list[MCPToolConfig]
    periodic_indexing_enabled: bool = False
    indexing_frequency_minutes: int | None = None

    def to_connector_create(self, search_space_id: int) -> SearchSourceConnectorCreate:
        """Convert to base SearchSourceConnectorCreate schema."""
        return SearchSourceConnectorCreate(
            name=self.name,
            connector_type=SearchSourceConnectorType.MCP_CONNECTOR,
            is_indexable=False,  # MCP connectors are not indexable
            config={"tools": [tool.model_dump() for tool in self.tools]},
            periodic_indexing_enabled=False,  # MCP connectors don't support periodic indexing
            indexing_frequency_minutes=None,
        )


class MCPConnectorUpdate(BaseModel):
    """Schema for updating an MCP connector."""

    name: str | None = None
    tools: list[MCPToolConfig] | None = None


class MCPConnectorRead(BaseModel):
    """Schema for reading an MCP connector with tools."""

    id: int
    name: str
    connector_type: SearchSourceConnectorType
    tools: list[MCPToolConfig]
    search_space_id: int
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_connector(cls, connector: SearchSourceConnectorRead) -> "MCPConnectorRead":
        """Convert from base SearchSourceConnectorRead."""
        config = connector.config or {}
        tools_data = config.get("tools", [])
        tools = [MCPToolConfig(**tool) for tool in tools_data]

        return cls(
            id=connector.id,
            name=connector.name,
            connector_type=connector.connector_type,
            tools=tools,
            search_space_id=connector.search_space_id,
            user_id=connector.user_id,
            created_at=connector.created_at,
            updated_at=connector.updated_at,
        )
