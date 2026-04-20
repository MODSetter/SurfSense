"""Parse Notion MCP tool responses into structured dicts.

The Notion MCP server returns responses as MCP TextContent where the
``text`` field contains JSON-stringified Notion API response data.
See: https://deepwiki.com/makenotion/notion-mcp-server/4.3-request-and-response-handling

This module extracts that JSON and normalises it into the same dict
format that ``NotionHistoryConnector`` methods return, so downstream
code (KB sync, tool factories) works unchanged.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

MCP_SERIALIZATION_ERROR_MARKERS = [
    "Expected array, received string",
    "Expected object, received string",
    "should be defined, instead was `undefined`",
]


def is_mcp_serialization_error(text: str) -> bool:
    """Return True if the MCP error text matches a known serialization bug."""
    return any(marker in text for marker in MCP_SERIALIZATION_ERROR_MARKERS)


def extract_text_from_mcp_response(response) -> str:
    """Pull the concatenated text out of an MCP ``CallToolResult``.

    Args:
        response: The ``CallToolResult`` returned by ``session.call_tool()``.

    Returns:
        Concatenated text content from the response.
    """
    parts: list[str] = []
    for content in response.content:
        if hasattr(content, "text"):
            parts.append(content.text)
        elif hasattr(content, "data"):
            parts.append(str(content.data))
        else:
            parts.append(str(content))
    return "\n".join(parts) if parts else ""


def _try_parse_json(text: str) -> dict[str, Any] | None:
    """Attempt to parse *text* as JSON, returning None on failure."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extract_page_title(page_data: dict[str, Any]) -> str:
    """Best-effort extraction of the page title from a Notion page object."""
    props = page_data.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return " ".join(t.get("plain_text", "") for t in title_parts)
    return page_data.get("id", "Untitled")


def parse_create_page_response(raw_text: str) -> dict[str, Any]:
    """Parse a ``notion-create-pages`` MCP response.

    Returns a dict compatible with ``NotionHistoryConnector.create_page()``:
    ``{status, page_id, url, title, message}``
    """
    data = _try_parse_json(raw_text)

    if data is None:
        if is_mcp_serialization_error(raw_text):
            return {
                "status": "mcp_error",
                "message": raw_text,
                "mcp_serialization_error": True,
            }
        return {"status": "error", "message": f"Unexpected MCP response: {raw_text[:500]}"}

    if data.get("status") == "error" or "error" in data:
        return {
            "status": "error",
            "message": data.get("message", data.get("error", str(data))),
        }

    page_id = data.get("id", "")
    url = data.get("url", "")
    title = _extract_page_title(data)

    return {
        "status": "success",
        "page_id": page_id,
        "url": url,
        "title": title,
        "message": f"Created Notion page '{title}'",
    }


def parse_update_page_response(raw_text: str) -> dict[str, Any]:
    """Parse a ``notion-update-page`` MCP response.

    Returns a dict compatible with ``NotionHistoryConnector.update_page()``:
    ``{status, page_id, url, title, message}``
    """
    data = _try_parse_json(raw_text)

    if data is None:
        if is_mcp_serialization_error(raw_text):
            return {
                "status": "mcp_error",
                "message": raw_text,
                "mcp_serialization_error": True,
            }
        return {"status": "error", "message": f"Unexpected MCP response: {raw_text[:500]}"}

    if data.get("status") == "error" or "error" in data:
        return {
            "status": "error",
            "message": data.get("message", data.get("error", str(data))),
        }

    page_id = data.get("id", "")
    url = data.get("url", "")
    title = _extract_page_title(data)

    return {
        "status": "success",
        "page_id": page_id,
        "url": url,
        "title": title,
        "message": f"Updated Notion page '{title}' (content appended)",
    }


def parse_delete_page_response(raw_text: str) -> dict[str, Any]:
    """Parse an archive (delete) MCP response.

    The Notion API responds to ``pages.update(archived=True)`` with
    the archived page object.

    Returns a dict compatible with ``NotionHistoryConnector.delete_page()``:
    ``{status, page_id, message}``
    """
    data = _try_parse_json(raw_text)

    if data is None:
        if is_mcp_serialization_error(raw_text):
            return {
                "status": "mcp_error",
                "message": raw_text,
                "mcp_serialization_error": True,
            }
        return {"status": "error", "message": f"Unexpected MCP response: {raw_text[:500]}"}

    if data.get("status") == "error" or "error" in data:
        return {
            "status": "error",
            "message": data.get("message", data.get("error", str(data))),
        }

    page_id = data.get("id", "")
    title = _extract_page_title(data)

    return {
        "status": "success",
        "page_id": page_id,
        "message": f"Deleted Notion page '{title}'",
    }


def parse_fetch_page_response(raw_text: str) -> dict[str, Any]:
    """Parse a ``notion-fetch`` MCP response.

    Returns the raw parsed dict (Notion page/block data) or an error dict.
    """
    data = _try_parse_json(raw_text)

    if data is None:
        return {"status": "error", "message": f"Unexpected MCP response: {raw_text[:500]}"}

    if data.get("status") == "error" or "error" in data:
        return {
            "status": "error",
            "message": data.get("message", data.get("error", str(data))),
        }

    return {"status": "success", "data": data}


def parse_health_check_response(raw_text: str) -> dict[str, Any]:
    """Parse a ``notion-get-self`` MCP response for health checking."""
    data = _try_parse_json(raw_text)

    if data is None:
        return {"status": "error", "message": raw_text[:500]}

    if data.get("status") == "error" or "error" in data:
        return {
            "status": "error",
            "message": data.get("message", data.get("error", str(data))),
        }

    return {"status": "success", "data": data}
