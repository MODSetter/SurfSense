import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.db import SearchSourceConnectorType
from app.schemas.google_auth_credentials import GoogleAuthCredentialsBase

from .base import IDModel, TimestampModel


class SearchSourceConnectorBase(BaseModel):
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None = None
    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def validate_config_for_connector_type(
        cls, config: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any]:
        connector_type = values.data.get("connector_type")

        if connector_type == SearchSourceConnectorType.SERPER_API:
            # For SERPER_API, only allow SERPER_API_KEY
            allowed_keys = ["SERPER_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For SERPER_API connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the API key is not empty
            if not config.get("SERPER_API_KEY"):
                raise ValueError("SERPER_API_KEY cannot be empty")

        elif connector_type == SearchSourceConnectorType.TAVILY_API:
            # For TAVILY_API, only allow TAVILY_API_KEY
            allowed_keys = ["TAVILY_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For TAVILY_API connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the API key is not empty
            if not config.get("TAVILY_API_KEY"):
                raise ValueError("TAVILY_API_KEY cannot be empty")

        elif connector_type == SearchSourceConnectorType.LINKUP_API:
            # For LINKUP_API, only allow LINKUP_API_KEY
            allowed_keys = ["LINKUP_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For LINKUP_API connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the API key is not empty
            if not config.get("LINKUP_API_KEY"):
                raise ValueError("LINKUP_API_KEY cannot be empty")

        elif connector_type == SearchSourceConnectorType.SLACK_CONNECTOR:
            # For SLACK_CONNECTOR, only allow SLACK_BOT_TOKEN
            allowed_keys = ["SLACK_BOT_TOKEN"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For SLACK_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the bot token is not empty
            if not config.get("SLACK_BOT_TOKEN"):
                raise ValueError("SLACK_BOT_TOKEN cannot be empty")

        elif connector_type == SearchSourceConnectorType.NOTION_CONNECTOR:
            # For NOTION_CONNECTOR, only allow NOTION_INTEGRATION_TOKEN
            allowed_keys = ["NOTION_INTEGRATION_TOKEN"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For NOTION_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the integration token is not empty
            if not config.get("NOTION_INTEGRATION_TOKEN"):
                raise ValueError("NOTION_INTEGRATION_TOKEN cannot be empty")

        elif connector_type == SearchSourceConnectorType.GITHUB_CONNECTOR:
            # For GITHUB_CONNECTOR, only allow GITHUB_PAT and repo_full_names
            allowed_keys = ["GITHUB_PAT", "repo_full_names"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For GITHUB_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the token is not empty
            if not config.get("GITHUB_PAT"):
                raise ValueError("GITHUB_PAT cannot be empty")

            # Ensure the repo_full_names is present and is a non-empty list
            repo_full_names = config.get("repo_full_names")
            if not isinstance(repo_full_names, list) or not repo_full_names:
                raise ValueError("repo_full_names must be a non-empty list of strings")

        elif connector_type == SearchSourceConnectorType.LINEAR_CONNECTOR:
            # For LINEAR_CONNECTOR, only allow LINEAR_API_KEY
            allowed_keys = ["LINEAR_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For LINEAR_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the token is not empty
            if not config.get("LINEAR_API_KEY"):
                raise ValueError("LINEAR_API_KEY cannot be empty")

        elif connector_type == SearchSourceConnectorType.DISCORD_CONNECTOR:
            # For DISCORD_CONNECTOR, only allow DISCORD_BOT_TOKEN
            allowed_keys = ["DISCORD_BOT_TOKEN"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For DISCORD_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the bot token is not empty
            if not config.get("DISCORD_BOT_TOKEN"):
                raise ValueError("DISCORD_BOT_TOKEN cannot be empty")
        elif connector_type == SearchSourceConnectorType.JIRA_CONNECTOR:
            # For JIRA_CONNECTOR, require JIRA_EMAIL, JIRA_API_TOKEN and JIRA_BASE_URL
            allowed_keys = ["JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_BASE_URL"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For JIRA_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the email is not empty
            if not config.get("JIRA_EMAIL"):
                raise ValueError("JIRA_EMAIL cannot be empty")

            # Ensure the API token is not empty
            if not config.get("JIRA_API_TOKEN"):
                raise ValueError("JIRA_API_TOKEN cannot be empty")

            # Ensure the base URL is not empty
            if not config.get("JIRA_BASE_URL"):
                raise ValueError("JIRA_BASE_URL cannot be empty")

        elif connector_type == SearchSourceConnectorType.CONFLUENCE_CONNECTOR:
            # For CONFLUENCE_CONNECTOR, only allow specific keys
            allowed_keys = [
                "CONFLUENCE_BASE_URL",
                "CONFLUENCE_EMAIL",
                "CONFLUENCE_API_TOKEN",
            ]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For CONFLUENCE_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the email is not empty
            if not config.get("CONFLUENCE_EMAIL"):
                raise ValueError("CONFLUENCE_EMAIL cannot be empty")

            # Ensure the API token is not empty
            if not config.get("CONFLUENCE_API_TOKEN"):
                raise ValueError("CONFLUENCE_API_TOKEN cannot be empty")

            # Ensure the base URL is not empty
            if not config.get("CONFLUENCE_BASE_URL"):
                raise ValueError("CONFLUENCE_BASE_URL cannot be empty")

        elif connector_type == SearchSourceConnectorType.CLICKUP_CONNECTOR:
            # For CLICKUP_CONNECTOR, only allow CLICKUP_API_TOKEN
            allowed_keys = ["CLICKUP_API_TOKEN"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For CLICKUP_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the API token is not empty
            if not config.get("CLICKUP_API_TOKEN"):
                raise ValueError("CLICKUP_API_TOKEN cannot be empty")

        elif connector_type == SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR:
            # Required fields
            required_keys = list(GoogleAuthCredentialsBase.model_fields.keys())

            for key in required_keys:
                if key not in config or config[key] in (None, ""):
                    raise ValueError(f"{key} is required and cannot be empty")

        elif connector_type == SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR:
            # Required fields for Gmail connector (same as Calendar - uses Google OAuth)
            required_keys = list(GoogleAuthCredentialsBase.model_fields.keys())

            for key in required_keys:
                if key not in config or config[key] in (None, ""):
                    raise ValueError(f"{key} is required and cannot be empty")

        elif connector_type == SearchSourceConnectorType.LUMA_CONNECTOR:
            # For LUMA_CONNECTOR, only allow LUMA_API_KEY
            allowed_keys = ["LUMA_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(
                    f"For LUMA_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
                )

            # Ensure the api key is not empty
            if not config.get("LUMA_API_KEY"):
                raise ValueError("LUMA_API_KEY cannot be empty")

        return config


class SearchSourceConnectorCreate(SearchSourceConnectorBase):
    pass


class SearchSourceConnectorUpdate(BaseModel):
    name: str | None = None
    connector_type: SearchSourceConnectorType | None = None
    is_indexable: bool | None = None
    last_indexed_at: datetime | None = None
    config: dict[str, Any] | None = None


class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
