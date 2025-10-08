"""
Validation utilities for SurfSense backend.

This module contains validation functions that were previously scattered across
different modules. It leverages the pyvalidators library where applicable
to avoid rewriting common validation logic.
"""

import re
from typing import Any

import validators
from fastapi import HTTPException


def validate_search_space_id(search_space_id: Any) -> int:
    """
    Validate and convert search_space_id to integer.
    
    Args:
        search_space_id: The search space ID to validate
        
    Returns:
        int: Validated search space ID
        
    Raises:
        HTTPException: If validation fails
    """
    if search_space_id is None:
        raise HTTPException(
            status_code=400, 
            detail="search_space_id is required"
        )
    
    if isinstance(search_space_id, bool):
        raise HTTPException(
            status_code=400,
            detail="search_space_id must be an integer, not a boolean"
        )
    
    if isinstance(search_space_id, int):
        if search_space_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a positive integer"
                
            )
        return search_space_id
    
    if isinstance(search_space_id, str):
        # Check if it's a valid integer string
        if not search_space_id.strip():
            raise HTTPException(
                status_code=400,
                detail="search_space_id cannot be empty"
            )
        
        # Check for valid integer format (no leading zeros, no decimal points)
        if not re.match(r'^[1-9]\d*$', search_space_id.strip()):
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a valid positive integer"
            )
        
        try:
            value = int(search_space_id.strip())
            if value <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="search_space_id must be a positive integer"
                )
            return value
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a valid integer"
            ) from None
    
    raise HTTPException(
        status_code=400,
        detail="search_space_id must be an integer or string representation of an integer"
    )


def validate_document_ids(document_ids: Any) -> list[int]:
    """
    Validate and convert document_ids to list of integers.
    
    Args:
        document_ids: The document IDs to validate
        
    Returns:
        List[int]: Validated list of document IDs
        
    Raises:
        HTTPException: If validation fails
    """
    if document_ids is None:
        return []
    
    if not isinstance(document_ids, list):
        raise HTTPException(
            status_code=400,
            detail="document_ids_to_add_in_context must be a list"
        )
    
    validated_ids = []
    for i, doc_id in enumerate(document_ids):
        if isinstance(doc_id, bool):
            raise HTTPException(
                status_code=400,
                detail=f"document_ids_to_add_in_context[{i}] must be an integer, not a boolean",
            )

        if isinstance(doc_id, int):
            if doc_id <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a positive integer"
                )
            validated_ids.append(doc_id)
        elif isinstance(doc_id, str):
            if not doc_id.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] cannot be empty"
                )
            
            if not re.match(r'^[1-9]\d*$', doc_id.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a valid positive integer"
                )
            
            try:
                value = int(doc_id.strip())
                if value <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"document_ids_to_add_in_context[{i}] must be a positive integer"
                    )
                validated_ids.append(value)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a valid integer"
                ) from None
        else:
            raise HTTPException(
                status_code=400,
                detail=f"document_ids_to_add_in_context[{i}] must be an integer or string representation of an integer"
            )
    
    return validated_ids


def validate_connectors(connectors: Any) -> list[str]:
    """
    Validate selected_connectors list.
    
    Args:
        connectors: The connectors to validate
        
    Returns:
        List[str]: Validated list of connector names
        
    Raises:
        HTTPException: If validation fails
    """
    if connectors is None:
        return []
    
    if not isinstance(connectors, list):
        raise HTTPException(
            status_code=400,
            detail="selected_connectors must be a list"
        )
    
    validated_connectors = []
    for i, connector in enumerate(connectors):
        if not isinstance(connector, str):
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] must be a string"
            )
        
        if not connector.strip():
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] cannot be empty"
            )
        
        trimmed = connector.strip()
        if not re.fullmatch(r'[\w\-_]+', trimmed):
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] contains invalid characters"
            )
        validated_connectors.append(trimmed)
    
    return validated_connectors


def validate_research_mode(research_mode: Any) -> str:
    """
    Validate research_mode parameter.
    
    Args:
        research_mode: The research mode to validate
        
    Returns:
        str: Validated research mode
        
    Raises:
        HTTPException: If validation fails
    """
    if research_mode is None:
        return "QNA"  # Default value
    
    if not isinstance(research_mode, str):
        raise HTTPException(
            status_code=400,
            detail="research_mode must be a string"
        )
    normalized_mode = research_mode.strip().upper()
    if not normalized_mode:
        raise HTTPException(
            status_code=400,
            detail="research_mode cannot be empty"
        )

    valid_modes = ["REPORT_GENERAL", "REPORT_DEEP", "REPORT_DEEPER", "QNA"]
    if normalized_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"research_mode must be one of: {', '.join(valid_modes)}"
        )
    return normalized_mode


def validate_search_mode(search_mode: Any) -> str:
    """
    Validate search_mode parameter.
    
    Args:
        search_mode: The search mode to validate
        
    Returns:
        str: Validated search mode
        
    Raises:
        HTTPException: If validation fails
    """
    if search_mode is None:
        return "CHUNKS"  # Default value
    
    if not isinstance(search_mode, str):
        raise HTTPException(
            status_code=400,
            detail="search_mode must be a string"
        )
    normalized_mode = search_mode.strip().upper()
    if not normalized_mode:
        raise HTTPException(
            status_code=400,
            detail="search_mode cannot be empty"
        )

    valid_modes = ["CHUNKS", "DOCUMENTS"]
    if normalized_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"search_mode must be one of: {', '.join(valid_modes)}"
        )
    return normalized_mode


def validate_messages(messages: Any) -> list[dict]:
    """
    Validate messages structure.
    
    Args:
        messages: The messages to validate
        
    Returns:
        List[dict]: Validated messages
        
    Raises:
        HTTPException: If validation fails
    """
    if not isinstance(messages, list):
        raise HTTPException(
            status_code=400,
            detail="messages must be a list"
        )
    
    if not messages:
        raise HTTPException(
            status_code=400,
            detail="messages cannot be empty"
        )
    
    validated_messages = []
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}] must be a dictionary"
            )
        
        if "role" not in message:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}] must have a 'role' field"
            )
        
        if "content" not in message:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}] must have a 'content' field"
            )
        
        role = message["role"]
        if not isinstance(role, str) or role not in ["user", "assistant", "system"]:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].role must be 'user', 'assistant', or 'system'"
            )
        
        content = message["content"]
        if not isinstance(content, str):
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].content must be a string"
            )
        
        if not content.strip():
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].content cannot be empty"
            )
        
        # Basic content sanitization
        sanitized_content = content.strip()
        if len(sanitized_content) > 10000:  # Reasonable limit
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].content is too long (max 10000 characters)"
            )
        
        validated_messages.append({
            "role": role,
            "content": sanitized_content
        })
    
    return validated_messages


def validate_email(email: str) -> str:
    """
    Validate email address using pyvalidators library.
    
    Args:
        email: The email address to validate
        
    Returns:
        str: Validated email address
        
    Raises:
        HTTPException: If validation fails
    """
    if not email or not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Email address is required"
        )
    
    email = email.strip()
    
    if not validators.email(email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email address format"
        )
    
    return email


def validate_url(url: str) -> str:
    """
    Validate URL using pyvalidators library.
    
    Args:
        url: The URL to validate
        
    Returns:
        str: Validated URL
        
    Raises:
        HTTPException: If validation fails
    """
    if not url or not url.strip():
        raise HTTPException(
            status_code=400,
            detail="URL is required"
        )
    
    url = url.strip()
    
    if not validators.url(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL format"
        )
    
    return url


def validate_uuid(uuid_string: str) -> str:
    """
    Validate UUID using pyvalidators library.
    
    Args:
        uuid_string: The UUID string to validate
        
    Returns:
        str: Validated UUID string
        
    Raises:
        HTTPException: If validation fails
    """
    if not uuid_string or not uuid_string.strip():
        raise HTTPException(
            status_code=400,
            detail="UUID is required"
        )
    
    uuid_string = uuid_string.strip()
    
    if not validators.uuid(uuid_string):
        raise HTTPException(
            status_code=400,
            detail="Invalid UUID format"
        )
    
    return uuid_string


def validate_connector_config(connector_type: str | Any, config: dict[str, Any]) -> dict[str, Any]:
    """
    Validate connector configuration based on connector type.
    
    Args:
        connector_type: The type of connector (string or enum)
        config: The configuration dictionary to validate
        
    Returns:
        dict: Validated configuration
        
    Raises:
        ValueError: If validation fails
    """
    # Convert enum to string if needed
    connector_type_str = str(connector_type).split('.')[-1] if hasattr(connector_type, 'value') else str(connector_type)
    
    if connector_type_str == "SERPER_API":
        # For SERPER_API, only allow SERPER_API_KEY
        allowed_keys = ["SERPER_API_KEY"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For SERPER_API connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the API key is not empty
        if not config.get("SERPER_API_KEY"):
            raise ValueError("SERPER_API_KEY cannot be empty")

    elif connector_type_str == "TAVILY_API":
        # For TAVILY_API, only allow TAVILY_API_KEY
        allowed_keys = ["TAVILY_API_KEY"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For TAVILY_API connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the API key is not empty
        if not config.get("TAVILY_API_KEY"):
            raise ValueError("TAVILY_API_KEY cannot be empty")

    elif connector_type_str == "LINKUP_API":
        # For LINKUP_API, only allow LINKUP_API_KEY
        allowed_keys = ["LINKUP_API_KEY"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For LINKUP_API connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the API key is not empty
        if not config.get("LINKUP_API_KEY"):
            raise ValueError("LINKUP_API_KEY cannot be empty")

    elif connector_type_str == "SLACK_CONNECTOR":
        # For SLACK_CONNECTOR, only allow SLACK_BOT_TOKEN
        allowed_keys = ["SLACK_BOT_TOKEN"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For SLACK_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the bot token is not empty
        if not config.get("SLACK_BOT_TOKEN"):
            raise ValueError("SLACK_BOT_TOKEN cannot be empty")

    elif connector_type_str == "NOTION_CONNECTOR":
        # For NOTION_CONNECTOR, only allow NOTION_INTEGRATION_TOKEN
        allowed_keys = ["NOTION_INTEGRATION_TOKEN"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For NOTION_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the integration token is not empty
        if not config.get("NOTION_INTEGRATION_TOKEN"):
            raise ValueError("NOTION_INTEGRATION_TOKEN cannot be empty")

    elif connector_type_str == "GITHUB_CONNECTOR":
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

    elif connector_type_str == "LINEAR_CONNECTOR":
        # For LINEAR_CONNECTOR, only allow LINEAR_API_KEY
        allowed_keys = ["LINEAR_API_KEY"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For LINEAR_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the token is not empty
        if not config.get("LINEAR_API_KEY"):
            raise ValueError("LINEAR_API_KEY cannot be empty")

    elif connector_type_str == "DISCORD_CONNECTOR":
        # For DISCORD_CONNECTOR, only allow DISCORD_BOT_TOKEN
        allowed_keys = ["DISCORD_BOT_TOKEN"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For DISCORD_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the bot token is not empty
        if not config.get("DISCORD_BOT_TOKEN"):
            raise ValueError("DISCORD_BOT_TOKEN cannot be empty")

    elif connector_type_str == "JIRA_CONNECTOR":
        # For JIRA_CONNECTOR, require JIRA_EMAIL, JIRA_API_TOKEN and JIRA_BASE_URL
        allowed_keys = ["JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_BASE_URL"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For JIRA_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Validate email format
        if not validators.email(config.get("JIRA_EMAIL", "")):
            raise ValueError("Invalid email format for JIRA connector")

        # Validate URL format
        if not validators.url(config.get("JIRA_BASE_URL", "")):
            raise ValueError("Invalid base URL format for JIRA connector")

        # Ensure the email is not empty
        if not config.get("JIRA_EMAIL"):
            raise ValueError("JIRA_EMAIL cannot be empty")

        # Ensure the API token is not empty
        if not config.get("JIRA_API_TOKEN"):
            raise ValueError("JIRA_API_TOKEN cannot be empty")

        # Ensure the base URL is not empty
        if not config.get("JIRA_BASE_URL"):
            raise ValueError("JIRA_BASE_URL cannot be empty")

    elif connector_type_str == "CONFLUENCE_CONNECTOR":
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

        # Validate email format
        if not validators.email(config.get("CONFLUENCE_EMAIL", "")):
            raise ValueError("Invalid email format for Confluence connector")

        # Validate URL format
        if not validators.url(config.get("CONFLUENCE_BASE_URL", "")):
            raise ValueError("Invalid base URL format for Confluence connector")

        # Ensure the email is not empty
        if not config.get("CONFLUENCE_EMAIL"):
            raise ValueError("CONFLUENCE_EMAIL cannot be empty")

        # Ensure the API token is not empty
        if not config.get("CONFLUENCE_API_TOKEN"):
            raise ValueError("CONFLUENCE_API_TOKEN cannot be empty")

        # Ensure the base URL is not empty
        if not config.get("CONFLUENCE_BASE_URL"):
            raise ValueError("CONFLUENCE_BASE_URL cannot be empty")

    elif connector_type_str == "CLICKUP_CONNECTOR":
        # For CLICKUP_CONNECTOR, only allow CLICKUP_API_TOKEN
        allowed_keys = ["CLICKUP_API_TOKEN"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For CLICKUP_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the API token is not empty
        if not config.get("CLICKUP_API_TOKEN"):
            raise ValueError("CLICKUP_API_TOKEN cannot be empty")

    elif connector_type_str == "GOOGLE_CALENDAR_CONNECTOR":
        # Required fields for Google Calendar connector
        required_keys = ["token", "refresh_token", "token_uri", "client_id", "expiry", "scopes", "client_secret"]
        
        for key in required_keys:
            if key not in config or config[key] in (None, ""):
                raise ValueError(f"{key} is required and cannot be empty")

    elif connector_type_str == "GOOGLE_GMAIL_CONNECTOR":
        # Required fields for Gmail connector (same as Calendar - uses Google OAuth)
        required_keys = ["token", "refresh_token", "token_uri", "client_id", "expiry", "scopes", "client_secret"]
        
        for key in required_keys:
            if key not in config or config[key] in (None, ""):
                raise ValueError(f"{key} is required and cannot be empty")

    elif connector_type_str == "AIRTABLE_CONNECTOR":
        # For AIRTABLE_CONNECTOR, only allow AIRTABLE_API_KEY and AIRTABLE_BASE_ID
        allowed_keys = ["AIRTABLE_API_KEY", "AIRTABLE_BASE_ID"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For AIRTABLE_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the API key is not empty
        if not config.get("AIRTABLE_API_KEY"):
            raise ValueError("AIRTABLE_API_KEY cannot be empty")

        # Ensure the base ID is not empty
        if not config.get("AIRTABLE_BASE_ID"):
            raise ValueError("AIRTABLE_BASE_ID cannot be empty")

    elif connector_type_str == "LUMA_CONNECTOR":
        # For LUMA_CONNECTOR, only allow LUMA_API_KEY
        allowed_keys = ["LUMA_API_KEY"]
        if set(config.keys()) != set(allowed_keys):
            raise ValueError(
                f"For LUMA_CONNECTOR connector type, config must only contain these keys: {allowed_keys}"
            )

        # Ensure the API key is not empty
        if not config.get("LUMA_API_KEY"):
            raise ValueError("LUMA_API_KEY cannot be empty")

    return config
