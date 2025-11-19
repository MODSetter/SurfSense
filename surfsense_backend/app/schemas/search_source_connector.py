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
        cls, config: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any]:
        connector_type = values.data.get("connector_type")
        return validate_connector_config(connector_type, config)

    @model_validator(mode="after")
    def validate_periodic_indexing(self):
        """Validate that periodic indexing configuration is consistent."""
        if self.periodic_indexing_enabled:
            if not self.is_indexable:
                raise ValueError(
                    "periodic_indexing_enabled can only be True for indexable connectors"
                )
            if self.indexing_frequency_minutes is None:
                raise ValueError(
                    "indexing_frequency_minutes is required when periodic_indexing_enabled is True"
                )
            if self.indexing_frequency_minutes <= 0:
                raise ValueError("indexing_frequency_minutes must be greater than 0")
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


# Sensitive config keys that should not be exposed in API responses
SENSITIVE_CONFIG_KEYS = {
    "token", "api_token", "api_key", "access_token", "secret", "password",
    "github_pat", "slack_bot_token", "slack_user_token", "slack_app_token",
    "jira_api_token", "confluence_api_token", "linear_api_key", "notion_api_key",
    "airtable_access_token", "discord_bot_token", "elasticsearch_api_key",
    "luma_api_key", "mastodon_access_token", "jellyfin_api_key",
    "home_assistant_token", "google_credentials", "credentials",
}


def sanitize_connector_config(config: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields from connector config for safe API responses"""
    if not config:
        return {}

    sanitized = {}
    for key, value in config.items():
        key_lower = key.lower()
        # Check if key contains any sensitive keyword
        is_sensitive = any(
            sensitive in key_lower
            for sensitive in SENSITIVE_CONFIG_KEYS
        )
        if is_sensitive:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_connector_config(value)
        else:
            sanitized[key] = value
    return sanitized


class SearchSourceConnectorReadSafe(BaseModel):
    """Safe response schema that excludes sensitive config values"""
    id: int
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None = None
    config: dict[str, Any]  # Sanitized config
    periodic_indexing_enabled: bool = False
    indexing_frequency_minutes: int | None = None
    next_scheduled_at: datetime | None = None
    search_space_id: int
    user_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_connector(cls, connector) -> "SearchSourceConnectorReadSafe":
        """Create safe response from SearchSourceConnector model"""
        return cls(
            id=connector.id,
            name=connector.name,
            connector_type=connector.connector_type,
            is_indexable=connector.is_indexable,
            last_indexed_at=connector.last_indexed_at,
            config=sanitize_connector_config(connector.config),
            periodic_indexing_enabled=connector.periodic_indexing_enabled,
            indexing_frequency_minutes=connector.indexing_frequency_minutes,
            next_scheduled_at=connector.next_scheduled_at,
            search_space_id=connector.search_space_id,
            user_id=connector.user_id,
            created_at=connector.created_at,
            updated_at=connector.updated_at,
        )
