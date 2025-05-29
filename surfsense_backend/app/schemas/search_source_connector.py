from datetime import datetime
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, field_validator, ConfigDict
from .base import IDModel, TimestampModel
from app.db import SearchSourceConnectorType

class SearchSourceConnectorBase(BaseModel):
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: Optional[datetime] = None
    config: Dict[str, Any]
    
    @field_validator('config')
    @classmethod
    def validate_config_for_connector_type(cls, config: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        connector_type = values.data.get('connector_type')
        
        if connector_type == SearchSourceConnectorType.SERPER_API:
            # For SERPER_API, only allow SERPER_API_KEY
            allowed_keys = ["SERPER_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(f"For SERPER_API connector type, config must only contain these keys: {allowed_keys}")
            
            # Ensure the API key is not empty
            if not config.get("SERPER_API_KEY"):
                raise ValueError("SERPER_API_KEY cannot be empty")
            
        elif connector_type == SearchSourceConnectorType.TAVILY_API:
            # For TAVILY_API, only allow TAVILY_API_KEY
            allowed_keys = ["TAVILY_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(f"For TAVILY_API connector type, config must only contain these keys: {allowed_keys}")
                
            # Ensure the API key is not empty
            if not config.get("TAVILY_API_KEY"):
                raise ValueError("TAVILY_API_KEY cannot be empty")
        
        elif connector_type == SearchSourceConnectorType.LINKUP_API:
            # For LINKUP_API, only allow LINKUP_API_KEY
            allowed_keys = ["LINKUP_API_KEY"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(f"For LINKUP_API connector type, config must only contain these keys: {allowed_keys}")
                
            # Ensure the API key is not empty
            if not config.get("LINKUP_API_KEY"):
                raise ValueError("LINKUP_API_KEY cannot be empty")
                
        elif connector_type == SearchSourceConnectorType.SLACK_CONNECTOR:
            # For SLACK_CONNECTOR, define allowed keys
            allowed_keys = [
                "SLACK_BOT_TOKEN",
                "slack_membership_filter_type",
                "slack_selected_channel_ids",
                "slack_periodic_indexing_frequency", # Renamed from slack_indexing_frequency
                "slack_initial_indexing_days",
                "slack_initial_max_messages_per_channel",
                "slack_periodic_indexing_enabled", # New field
                "slack_max_messages_per_channel_periodic" # New field
            ]

            # Ensure SLACK_BOT_TOKEN is always present and not empty
            if not config.get("SLACK_BOT_TOKEN"):
                raise ValueError("SLACK_BOT_TOKEN is mandatory and cannot be empty for SLACK_CONNECTOR")

            # Check that all provided config keys are allowed
            for key in config:
                if key not in allowed_keys:
                    raise ValueError(f"Key '{key}' is not allowed for SLACK_CONNECTOR. Allowed keys are: {allowed_keys}")

            # Validate slack_membership_filter_type
            if "slack_membership_filter_type" in config:
                filter_type = config.get("slack_membership_filter_type")
                if not isinstance(filter_type, str):
                    raise ValueError("slack_membership_filter_type must be a string")
                if filter_type not in ["all_member_channels", "selected_member_channels"]:
                    raise ValueError("slack_membership_filter_type must be 'all_member_channels' or 'selected_member_channels'")

            # Validate slack_selected_channel_ids
            if config.get("slack_membership_filter_type") == "selected_member_channels":
                if "slack_selected_channel_ids" not in config:
                    raise ValueError("slack_selected_channel_ids is required when slack_membership_filter_type is 'selected_member_channels'")
                selected_channels = config.get("slack_selected_channel_ids")
                if not isinstance(selected_channels, list) or not all(isinstance(item, str) for item in selected_channels):
                    raise ValueError("slack_selected_channel_ids must be a list of strings")
            elif "slack_selected_channel_ids" in config and config.get("slack_membership_filter_type") == "all_member_channels":
                # Optional: could remove it or just ignore it if filter type is all_member_channels
                pass # For now, just allow it to be present but not validated for content
            
            # Validate slack_periodic_indexing_enabled
            if "slack_periodic_indexing_enabled" in config and not isinstance(config.get("slack_periodic_indexing_enabled"), bool):
                raise ValueError("slack_periodic_indexing_enabled must be a boolean")

            # Validate slack_periodic_indexing_frequency
            # This field is only required if slack_periodic_indexing_enabled is True
            periodic_indexing_enabled = config.get("slack_periodic_indexing_enabled", False) # Default to False if not provided
            if periodic_indexing_enabled:
                if "slack_periodic_indexing_frequency" not in config:
                    raise ValueError("slack_periodic_indexing_frequency is required when slack_periodic_indexing_enabled is True")
                
                freq = config.get("slack_periodic_indexing_frequency")
                if not isinstance(freq, str):
                    raise ValueError("slack_periodic_indexing_frequency must be a string")
                # Example valid values, adjust as needed
                if freq not in ["daily", "weekly", "monthly"]:
                    raise ValueError("slack_periodic_indexing_frequency must be one of 'daily', 'weekly', 'monthly'")
            elif "slack_periodic_indexing_frequency" in config:
                 # If periodic indexing is not enabled, but frequency is provided, it should still be a string
                if not isinstance(config.get("slack_periodic_indexing_frequency"), str):
                    raise ValueError("slack_periodic_indexing_frequency must be a string")


            # Validate slack_max_messages_per_channel_periodic
            if "slack_max_messages_per_channel_periodic" in config:
                max_messages_periodic = config.get("slack_max_messages_per_channel_periodic")
                if not isinstance(max_messages_periodic, int):
                    raise ValueError("slack_max_messages_per_channel_periodic must be an integer")
                if max_messages_periodic <= 0:
                    raise ValueError("slack_max_messages_per_channel_periodic must be greater than 0")

            # Validate slack_initial_indexing_days
            if "slack_initial_indexing_days" in config and not isinstance(config.get("slack_initial_indexing_days"), int):
                raise ValueError("slack_initial_indexing_days must be an integer")

            # Validate slack_initial_max_messages_per_channel
            if "slack_initial_max_messages_per_channel" in config and not isinstance(config.get("slack_initial_max_messages_per_channel"), int):
                raise ValueError("slack_initial_max_messages_per_channel must be an integer")
            
        elif connector_type == SearchSourceConnectorType.NOTION_CONNECTOR:
            # For NOTION_CONNECTOR, only allow NOTION_INTEGRATION_TOKEN
            allowed_keys = ["NOTION_INTEGRATION_TOKEN"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(f"For NOTION_CONNECTOR connector type, config must only contain these keys: {allowed_keys}")
            
            # Ensure the integration token is not empty
            if not config.get("NOTION_INTEGRATION_TOKEN"):
                raise ValueError("NOTION_INTEGRATION_TOKEN cannot be empty")
        
        elif connector_type == SearchSourceConnectorType.GITHUB_CONNECTOR:
            # For GITHUB_CONNECTOR, only allow GITHUB_PAT and repo_full_names
            allowed_keys = ["GITHUB_PAT", "repo_full_names"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(f"For GITHUB_CONNECTOR connector type, config must only contain these keys: {allowed_keys}")
        
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
                raise ValueError(f"For LINEAR_CONNECTOR connector type, config must only contain these keys: {allowed_keys}")
        
            # Ensure the token is not empty
            if not config.get("LINEAR_API_KEY"):
                raise ValueError("LINEAR_API_KEY cannot be empty")

        return config

class SearchSourceConnectorCreate(SearchSourceConnectorBase):
    pass

class SearchSourceConnectorUpdate(BaseModel):
    name: Optional[str] = None
    connector_type: Optional[SearchSourceConnectorType] = None
    is_indexable: Optional[bool] = None
    last_indexed_at: Optional[datetime] = None
    config: Optional[Dict[str, Any]] = None

class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True) 
