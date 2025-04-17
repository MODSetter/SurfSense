from datetime import datetime
import uuid
from typing import Dict, Any
from pydantic import BaseModel, field_validator
from .base import IDModel, TimestampModel
from app.db import SearchSourceConnectorType

class SearchSourceConnectorBase(BaseModel):
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None
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
                
        elif connector_type == SearchSourceConnectorType.SLACK_CONNECTOR:
            # For SLACK_CONNECTOR, only allow SLACK_BOT_TOKEN
            allowed_keys = ["SLACK_BOT_TOKEN"]
            if set(config.keys()) != set(allowed_keys):
                raise ValueError(f"For SLACK_CONNECTOR connector type, config must only contain these keys: {allowed_keys}")

            # Ensure the bot token is not empty
            if not config.get("SLACK_BOT_TOKEN"):
                raise ValueError("SLACK_BOT_TOKEN cannot be empty")
            
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

        return config

class SearchSourceConnectorCreate(SearchSourceConnectorBase):
    pass

class SearchSourceConnectorUpdate(SearchSourceConnectorBase):
    pass

class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    user_id: uuid.UUID

    class Config:
        from_attributes = True 
