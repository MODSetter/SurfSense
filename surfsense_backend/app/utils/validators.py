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
        raise HTTPException(status_code=400, detail="search_space_id is required")

    if isinstance(search_space_id, bool):
        raise HTTPException(
            status_code=400, detail="search_space_id must be an integer, not a boolean"
        )

    if isinstance(search_space_id, int):
        if search_space_id <= 0:
            raise HTTPException(
                status_code=400, detail="search_space_id must be a positive integer"
            )
        return search_space_id

    if isinstance(search_space_id, str):
        # Check if it's a valid integer string
        if not search_space_id.strip():
            raise HTTPException(
                status_code=400, detail="search_space_id cannot be empty"
            )

        # Check for valid integer format (no leading zeros, no decimal points)
        if not re.match(r"^[1-9]\d*$", search_space_id.strip()):
            raise HTTPException(
                status_code=400,
                detail="search_space_id must be a valid positive integer",
            )

        value = int(search_space_id.strip())
        # Regex already guarantees value > 0, but check retained for clarity
        if value <= 0:
            raise HTTPException(
                status_code=400, detail="search_space_id must be a positive integer"
            )
        return value

    raise HTTPException(
        status_code=400,
        detail="search_space_id must be an integer or string representation of an integer",
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
            status_code=400, detail="document_ids_to_add_in_context must be a list"
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
                    detail=f"document_ids_to_add_in_context[{i}] must be a positive integer",
                )
            validated_ids.append(doc_id)
        elif isinstance(doc_id, str):
            if not doc_id.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] cannot be empty",
                )

            if not re.match(r"^[1-9]\d*$", doc_id.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a valid positive integer",
                )

            value = int(doc_id.strip())
            # Regex already guarantees value > 0
            if value <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"document_ids_to_add_in_context[{i}] must be a positive integer",
                )
            validated_ids.append(value)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"document_ids_to_add_in_context[{i}] must be an integer or string representation of an integer",
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
            status_code=400, detail="selected_connectors must be a list"
        )

    validated_connectors = []
    for i, connector in enumerate(connectors):
        if not isinstance(connector, str):
            raise HTTPException(
                status_code=400, detail=f"selected_connectors[{i}] must be a string"
            )

        if not connector.strip():
            raise HTTPException(
                status_code=400, detail=f"selected_connectors[{i}] cannot be empty"
            )

        trimmed = connector.strip()
        if not re.fullmatch(r"[\w\-_]+", trimmed):
            raise HTTPException(
                status_code=400,
                detail=f"selected_connectors[{i}] contains invalid characters",
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
        raise HTTPException(status_code=400, detail="research_mode must be a string")
    normalized_mode = research_mode.strip().upper()
    if not normalized_mode:
        raise HTTPException(status_code=400, detail="research_mode cannot be empty")

    valid_modes = ["QNA"]
    if normalized_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"research_mode must be one of: {', '.join(valid_modes)}",
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
        raise HTTPException(status_code=400, detail="search_mode must be a string")
    normalized_mode = search_mode.strip().upper()
    if not normalized_mode:
        raise HTTPException(status_code=400, detail="search_mode cannot be empty")

    valid_modes = ["CHUNKS", "DOCUMENTS"]
    if normalized_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"search_mode must be one of: {', '.join(valid_modes)}",
        )
    return normalized_mode


def validate_top_k(top_k: Any) -> int:
    """
    Validate and convert top_k to integer.

    Args:
        top_k: The top_k value to validate

    Returns:
        int: Validated top_k value (defaults to 10 if None)

    Raises:
        HTTPException: If validation fails
    """
    if top_k is None:
        return 10  # Default value

    if isinstance(top_k, bool):
        raise HTTPException(
            status_code=400, detail="top_k must be an integer, not a boolean"
        )

    if isinstance(top_k, int):
        if top_k <= 0:
            raise HTTPException(
                status_code=400, detail="top_k must be a positive integer"
            )
        if top_k > 100:
            raise HTTPException(status_code=400, detail="top_k must not exceed 100")
        return top_k

    if isinstance(top_k, str):
        if not top_k.strip():
            raise HTTPException(status_code=400, detail="top_k cannot be empty")

        if not re.match(r"^[1-9]\d*$", top_k.strip()):
            raise HTTPException(
                status_code=400, detail="top_k must be a valid positive integer"
            )

        value = int(top_k.strip())
        if value <= 0:
            raise HTTPException(
                status_code=400, detail="top_k must be a positive integer"
            )
        if value > 100:
            raise HTTPException(status_code=400, detail="top_k must not exceed 100")
        return value

    raise HTTPException(
        status_code=400,
        detail="top_k must be an integer or string representation of an integer",
    )


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
        raise HTTPException(status_code=400, detail="messages must be a list")

    if not messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    validated_messages = []
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise HTTPException(
                status_code=400, detail=f"messages[{i}] must be a dictionary"
            )

        if "role" not in message:
            raise HTTPException(
                status_code=400, detail=f"messages[{i}] must have a 'role' field"
            )

        if "content" not in message:
            raise HTTPException(
                status_code=400, detail=f"messages[{i}] must have a 'content' field"
            )

        role = message["role"]
        if not isinstance(role, str) or role not in ["user", "assistant", "system"]:
            raise HTTPException(
                status_code=400,
                detail=f"messages[{i}].role must be 'user', 'assistant', or 'system'",
            )

        content = message["content"]
        if not isinstance(content, str):
            raise HTTPException(
                status_code=400, detail=f"messages[{i}].content must be a string"
            )

        if not content.strip():
            raise HTTPException(
                status_code=400, detail=f"messages[{i}].content cannot be empty"
            )

        # Trim content
        sanitized_content = content.strip()

        validated_messages.append({"role": role, "content": sanitized_content})

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
        raise HTTPException(status_code=400, detail="Email address is required")

    email = email.strip()

    if not validators.email(email):
        raise HTTPException(status_code=400, detail="Invalid email address format")

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
        raise HTTPException(status_code=400, detail="URL is required")

    url = url.strip()

    if not validators.url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format")

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
        raise HTTPException(status_code=400, detail="UUID is required")

    uuid_string = uuid_string.strip()

    if not validators.uuid(uuid_string):
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    return uuid_string


def validate_connector_config(
    connector_type: str | Any, config: dict[str, Any]
) -> dict[str, Any]:
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
    if not isinstance(config, dict) or isinstance(config, bool):
        raise ValueError("config must be a dictionary of connector settings")

    # Convert enum to string if needed
    connector_type_str = (
        str(connector_type).split(".")[-1]
        if hasattr(connector_type, "value")
        else str(connector_type)
    )

    # Validation function helpers
    def validate_email_field(key: str, connector_name: str) -> None:
        if not validators.email(config.get(key, "")):
            raise ValueError(f"Invalid email format for {connector_name} connector")

    def validate_url_field(key: str, connector_name: str) -> None:
        if not validators.url(config.get(key, "").strip(), simple_host=True):
            raise ValueError(f"Invalid base URL format for {connector_name} connector")

    def validate_list_field(key: str, field_name: str) -> None:
        value = config.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field_name} must be a non-empty list of strings")

    # Lookup table for connector validation rules
    connector_rules = {
        "SERPER_API": {"required": ["SERPER_API_KEY"], "validators": {}},
        "TAVILY_API": {"required": ["TAVILY_API_KEY"], "validators": {}},
        "SEARXNG_API": {
            "required": ["SEARXNG_HOST"],
            "optional": [
                "SEARXNG_API_KEY",
                "SEARXNG_ENGINES",
                "SEARXNG_CATEGORIES",
                "SEARXNG_LANGUAGE",
                "SEARXNG_SAFESEARCH",
                "SEARXNG_VERIFY_SSL",
            ],
            "validators": {
                "SEARXNG_HOST": lambda: validate_url_field("SEARXNG_HOST", "SearxNG")
            },
        },
        "LINKUP_API": {"required": ["LINKUP_API_KEY"], "validators": {}},
        "BAIDU_SEARCH_API": {
            "required": ["BAIDU_API_KEY"],
            "optional": [
                "BAIDU_MODEL",
                "BAIDU_SEARCH_SOURCE",
                "BAIDU_ENABLE_DEEP_SEARCH",
            ],
            "validators": {},
        },
        "SLACK_CONNECTOR": {"required": ["SLACK_BOT_TOKEN"], "validators": {}},
        "NOTION_CONNECTOR": {
            "required": ["NOTION_INTEGRATION_TOKEN"],
            "validators": {},
        },
        "GITHUB_CONNECTOR": {
            "required": ["GITHUB_PAT", "repo_full_names"],
            "validators": {
                "repo_full_names": lambda: validate_list_field(
                    "repo_full_names", "repo_full_names"
                )
            },
        },
        "LINEAR_CONNECTOR": {"required": ["LINEAR_API_KEY"], "validators": {}},
        "DISCORD_CONNECTOR": {"required": ["DISCORD_BOT_TOKEN"], "validators": {}},
        "JIRA_CONNECTOR": {
            "required": ["JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_BASE_URL"],
            "validators": {
                "JIRA_EMAIL": lambda: validate_email_field("JIRA_EMAIL", "JIRA"),
                "JIRA_BASE_URL": lambda: validate_url_field("JIRA_BASE_URL", "JIRA"),
            },
        },
        "CONFLUENCE_CONNECTOR": {
            "required": [
                "CONFLUENCE_BASE_URL",
                "CONFLUENCE_EMAIL",
                "CONFLUENCE_API_TOKEN",
            ],
            "validators": {
                "CONFLUENCE_EMAIL": lambda: validate_email_field(
                    "CONFLUENCE_EMAIL", "Confluence"
                ),
                "CONFLUENCE_BASE_URL": lambda: validate_url_field(
                    "CONFLUENCE_BASE_URL", "Confluence"
                ),
            },
        },
        "CLICKUP_CONNECTOR": {"required": ["CLICKUP_API_TOKEN"], "validators": {}},
        # "GOOGLE_CALENDAR_CONNECTOR": {
        #     "required": ["token", "refresh_token", "token_uri", "client_id", "expiry", "scopes", "client_secret"],
        #     "validators": {},
        #     "allow_none_or_empty": False  # Special flag for Google connectors
        # },
        # "GOOGLE_GMAIL_CONNECTOR": {
        #     "required": ["token", "refresh_token", "token_uri", "client_id", "expiry", "scopes", "client_secret"],
        #     "validators": {},
        #     "allow_none_or_empty": False
        # },
        # "AIRTABLE_CONNECTOR": {
        #     "required": ["AIRTABLE_API_KEY", "AIRTABLE_BASE_ID"],
        #     "validators": {}
        # },
        "LUMA_CONNECTOR": {"required": ["LUMA_API_KEY"], "validators": {}},
    }

    rules = connector_rules.get(connector_type_str)
    if not rules:
        return config  # Unknown connector type, pass through

    required_keys = set(rules["required"])
    optional_keys = set(rules.get("optional", []))
    config_keys = set(config.keys())

    # Validate that no unexpected keys are present
    if not config_keys.issubset(required_keys | optional_keys):
        allowed_keys = list(required_keys | optional_keys)
        raise ValueError(
            f"For {connector_type_str} connector type, config may only contain these keys: {allowed_keys}"
        )

    # Validate that all required keys are present
    if not required_keys.issubset(config_keys):
        raise ValueError(
            f"For {connector_type_str} connector type, config must include these keys: {sorted(required_keys)}"
        )

    # Apply custom validators first (these check format before emptiness)
    for validator_func in rules["validators"].values():
        validator_func()

    # Validate each field is not empty
    for key in rules["required"]:
        # Special handling for Google connectors that don't allow None or empty strings
        if rules.get("allow_none_or_empty") is False:
            if key not in config or config[key] in (None, ""):
                raise ValueError(f"{key} is required and cannot be empty")
        else:
            # Standard check: field must have a truthy value
            if not config.get(key):
                raise ValueError(f"{key} cannot be empty")

    return config
