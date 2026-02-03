"""
Composio Service Module.

Provides a wrapper around the Composio SDK for managing OAuth connections
and executing tools for various integrations (Google Drive, Gmail, Calendar, etc.).
"""

import logging
from typing import Any

from composio import Composio

from app.config import config

logger = logging.getLogger(__name__)


# Mapping of toolkit IDs to their display names
COMPOSIO_TOOLKIT_NAMES = {
    "googledrive": "Google Drive",
    "gmail": "Gmail",
    "googlecalendar": "Google Calendar",
    "slack": "Slack",
    "notion": "Notion",
    "github": "GitHub",
}

# Toolkits that support indexing (Phase 1: Google services only)
INDEXABLE_TOOLKITS = {"googledrive", "gmail", "googlecalendar"}

# Mapping of toolkit IDs to connector types
TOOLKIT_TO_CONNECTOR_TYPE = {
    "googledrive": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "gmail": "COMPOSIO_GMAIL_CONNECTOR",
    "googlecalendar": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
}

# Mapping of toolkit IDs to document types
TOOLKIT_TO_DOCUMENT_TYPE = {
    "googledrive": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "gmail": "COMPOSIO_GMAIL_CONNECTOR",
    "googlecalendar": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
}

# Mapping of toolkit IDs to their indexer functions
# Format: toolkit_id -> (module_path, function_name, supports_date_filter)
# supports_date_filter: True if the indexer accepts start_date/end_date params
TOOLKIT_TO_INDEXER = {
    "googledrive": (
        "app.connectors.composio_google_drive_connector",
        "index_composio_google_drive",
        False,  # Google Drive doesn't use date filtering
    ),
    "gmail": (
        "app.connectors.composio_gmail_connector",
        "index_composio_gmail",
        True,  # Gmail uses date filtering
    ),
    "googlecalendar": (
        "app.connectors.composio_google_calendar_connector",
        "index_composio_google_calendar",
        True,  # Calendar uses date filtering
    ),
}


class ComposioService:
    """Service for interacting with Composio API."""

    # Default download directory for files from Composio
    DEFAULT_DOWNLOAD_DIR = "/tmp/composio_downloads"

    def __init__(
        self, api_key: str | None = None, file_download_dir: str | None = None
    ):
        """
        Initialize the Composio service.

        Args:
            api_key: Composio API key. If not provided, uses config.COMPOSIO_API_KEY.
            file_download_dir: Directory for downloaded files. Defaults to /tmp/composio_downloads.
        """
        import os

        self.api_key = api_key or config.COMPOSIO_API_KEY
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY is required but not configured")

        # Set up download directory
        self.file_download_dir = file_download_dir or self.DEFAULT_DOWNLOAD_DIR
        os.makedirs(self.file_download_dir, exist_ok=True)

        # Initialize Composio client with download directory
        # Per docs: file_download_dir configures where files are downloaded
        self.client = Composio(
            api_key=self.api_key, file_download_dir=self.file_download_dir
        )

    @staticmethod
    def is_enabled() -> bool:
        """Check if Composio integration is enabled."""
        return config.COMPOSIO_ENABLED and bool(config.COMPOSIO_API_KEY)

    def list_available_toolkits(self) -> list[dict[str, Any]]:
        """
        List all available Composio toolkits for the UI.

        Returns:
            List of toolkit metadata dictionaries.
        """
        toolkits = []
        for toolkit_id, display_name in COMPOSIO_TOOLKIT_NAMES.items():
            toolkits.append(
                {
                    "id": toolkit_id,
                    "name": display_name,
                    "is_indexable": toolkit_id in INDEXABLE_TOOLKITS,
                    "description": f"Connect to {display_name} via Composio",
                }
            )
        return toolkits

    def _get_auth_config_for_toolkit(self, toolkit_id: str) -> str | None:
        """
        Get the auth_config_id for a specific toolkit.

        Args:
            toolkit_id: The toolkit ID (e.g., "googledrive", "gmail").

        Returns:
            The auth_config_id or None if not found.
        """
        try:
            # List all auth configs and find the one matching our toolkit
            auth_configs = self.client.auth_configs.list()
            for auth_config in auth_configs.items:
                # Get toolkit - it may be an object with a 'slug' or 'name' attribute, or a string
                config_toolkit = getattr(auth_config, "toolkit", None)
                if config_toolkit is None:
                    continue

                # Extract toolkit name/slug from the object
                toolkit_name = None
                if isinstance(config_toolkit, str):
                    toolkit_name = config_toolkit
                elif hasattr(config_toolkit, "slug"):
                    toolkit_name = config_toolkit.slug
                elif hasattr(config_toolkit, "name"):
                    toolkit_name = config_toolkit.name
                elif hasattr(config_toolkit, "id"):
                    toolkit_name = config_toolkit.id

                # Compare case-insensitively
                if toolkit_name and toolkit_name.lower() == toolkit_id.lower():
                    logger.info(
                        f"Found auth config {auth_config.id} for toolkit {toolkit_id}"
                    )
                    return auth_config.id

            # Log available auth configs for debugging
            logger.warning(
                f"No auth config found for toolkit '{toolkit_id}'. Available auth configs:"
            )
            for auth_config in auth_configs.items:
                config_toolkit = getattr(auth_config, "toolkit", None)
                logger.warning(f"  - {auth_config.id}: toolkit={config_toolkit}")

            return None
        except Exception as e:
            logger.error(f"Failed to list auth configs: {e!s}")
            return None

    async def initiate_connection(
        self,
        user_id: str,
        toolkit_id: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """
        Initiate OAuth flow for a Composio toolkit.

        Args:
            user_id: Unique identifier for the user (used as entity_id in Composio).
            toolkit_id: The toolkit to connect (e.g., "googledrive", "gmail").
            redirect_uri: URL to redirect after OAuth completion.

        Returns:
            Dictionary containing redirect_url and connection_id.
        """
        if toolkit_id not in COMPOSIO_TOOLKIT_NAMES:
            raise ValueError(f"Unknown toolkit: {toolkit_id}")

        try:
            # First, get the auth_config_id for this toolkit
            auth_config_id = self._get_auth_config_for_toolkit(toolkit_id)

            if not auth_config_id:
                raise ValueError(
                    f"No auth config found for toolkit '{toolkit_id}'. "
                    f"Please create an auth config for {COMPOSIO_TOOLKIT_NAMES.get(toolkit_id, toolkit_id)} "
                    f"in your Composio dashboard at https://app.composio.dev"
                )

            # Initiate the connection using Composio SDK with auth_config_id
            # allow_multiple=True allows creating multiple connections per user (e.g., different Google accounts)
            connection_request = self.client.connected_accounts.initiate(
                user_id=user_id,
                auth_config_id=auth_config_id,
                callback_url=redirect_uri,
                allow_multiple=True,
            )

            logger.info(
                f"Initiated Composio connection for user {user_id}, toolkit {toolkit_id}, auth_config {auth_config_id}"
            )

            return {
                "redirect_url": connection_request.redirect_url,
                "connection_id": getattr(connection_request, "id", None),
            }

        except Exception as e:
            logger.error(f"Failed to initiate Composio connection: {e!s}")
            raise

    async def delete_connected_account(self, connected_account_id: str) -> bool:
        """
        Delete a connected account from Composio.

        This permanently removes the connected account and revokes access tokens.

        Args:
            connected_account_id: The Composio connected account ID to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        try:
            self.client.connected_accounts.delete(connected_account_id)
            logger.info(
                f"Successfully deleted Composio connected account: {connected_account_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete Composio connected account {connected_account_id}: {e!s}"
            )
            return False

    async def execute_tool(
        self,
        connected_account_id: str,
        tool_name: str,
        params: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a Composio tool.

        Args:
            connected_account_id: The connected account to use.
            tool_name: Name of the tool (e.g., "GOOGLEDRIVE_LIST_FILES").
            params: Parameters for the tool.
            entity_id: The entity/user ID that owns the connected account.

        Returns:
            Tool execution result.
        """
        try:
            # Based on Composio SDK docs:
            # - slug: tool name
            # - arguments: tool parameters
            # - connected_account_id: for authentication
            # - user_id: user identifier (SDK uses user_id, not entity_id)
            # - dangerously_skip_version_check: skip version check for manual execution
            result = self.client.tools.execute(
                slug=tool_name,
                connected_account_id=connected_account_id,
                user_id=entity_id,  # SDK expects user_id parameter
                arguments=params or {},
                dangerously_skip_version_check=True,
            )
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e!s}")
            return {"success": False, "error": str(e)}

    # ===== Google Drive specific methods =====

    async def get_drive_files(
        self,
        connected_account_id: str,
        entity_id: str,
        folder_id: str | None = None,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        List files from Google Drive via Composio.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            folder_id: Optional folder ID to list contents of.
            page_token: Pagination token.
            page_size: Number of files per page.

        Returns:
            Tuple of (files list, next_page_token, error message).
        """
        try:
            # Composio uses snake_case for parameters
            # IMPORTANT: Include 'fields' to ensure mimeType is returned in the response
            # Without this, Google Drive API may not include mimeType for some files
            params = {
                "page_size": min(page_size, 100),
                "fields": "files(id,name,mimeType,modifiedTime,createdTime),nextPageToken",
            }
            if folder_id:
                # List contents of a specific folder (exclude shortcuts - we don't have access to them)
                params["q"] = (
                    f"'{folder_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.shortcut'"
                )
            else:
                # List root-level items only (My Drive root), exclude shortcuts
                params["q"] = (
                    "'root' in parents and trashed = false and mimeType != 'application/vnd.google-apps.shortcut'"
                )
            if page_token:
                params["page_token"] = page_token

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_LIST_FILES",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], None, result.get("error", "Unknown error")

            data = result.get("data", {})

            # Handle nested response structure from Composio
            files = []
            next_token = None
            if isinstance(data, dict):
                # Try direct access first, then nested
                files = data.get("files", []) or data.get("data", {}).get("files", [])
                next_token = (
                    data.get("nextPageToken")
                    or data.get("next_page_token")
                    or data.get("data", {}).get("nextPageToken")
                )
            elif isinstance(data, list):
                files = data

            return files, next_token, None

        except Exception as e:
            logger.error(f"Failed to list Drive files: {e!s}")
            return [], None, str(e)

    async def get_drive_file_content(
        self,
        connected_account_id: str,
        entity_id: str,
        file_id: str,
        original_mime_type: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """
        Download file content from Google Drive via Composio.

        Per Composio docs: When tools return files, they are automatically downloaded
        to a local directory, and the local file path is provided in the response.
        Response includes: file_path, file_name, size fields.

        For Google Workspace files (Docs, Sheets, Slides), exports to PDF format.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            file_id: Google Drive file ID.
            original_mime_type: Original MIME type of the file (used to detect Google Workspace files).

        Returns:
            Tuple of (file content bytes, error message).
        """
        from pathlib import Path

        try:
            params = {"file_id": file_id}

            # For Google Workspace files, explicitly export as PDF
            # This ensures consistent behavior and proper binary detection
            if original_mime_type and original_mime_type.startswith(
                "application/vnd.google-apps."
            ):
                params["mime_type"] = "application/pdf"

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_DOWNLOAD_FILE",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data")
            if not data:
                return None, "No data returned from Composio"

            # Per Composio docs, response includes file_path where file was downloaded
            # Response structure: {data: {...}, error: ..., successful: ...}
            # The actual file info is nested inside data["data"]
            file_path = None

            if isinstance(data, dict):
                # Handle nested response structure: data contains {data, error, successful}
                # The actual file info is in data["data"]
                inner_data = data
                if "data" in data and isinstance(data["data"], dict):
                    inner_data = data["data"]
                    logger.debug(
                        f"Found nested data structure. Inner keys: {list(inner_data.keys())}"
                    )
                elif "successful" in data and "data" in data:
                    # Standard Composio response wrapper
                    inner_data = data["data"] if data["data"] else data

                # Try documented fields: file_path, downloaded_file_content, path, uri
                file_path = (
                    inner_data.get("file_path")
                    or inner_data.get("downloaded_file_content")
                    or inner_data.get("path")
                    or inner_data.get("uri")
                )

                # Handle nested dict case where downloaded_file_content contains the path
                if isinstance(file_path, dict):
                    file_path = (
                        file_path.get("file_path")
                        or file_path.get("downloaded_file_content")
                        or file_path.get("path")
                        or file_path.get("uri")
                    )

                # If still no path, check if inner_data itself has the nested structure
                if not file_path and isinstance(inner_data, dict):
                    for key in ["downloaded_file_content", "file_path", "path", "uri"]:
                        if key in inner_data:
                            val = inner_data[key]
                            if isinstance(val, str):
                                file_path = val
                                break
                            elif isinstance(val, dict):
                                # One more level of nesting
                                file_path = (
                                    val.get("file_path")
                                    or val.get("downloaded_file_content")
                                    or val.get("path")
                                    or val.get("uri")
                                )
                                if file_path:
                                    break

                logger.debug(
                    f"Composio response keys: {list(data.keys())}, inner keys: {list(inner_data.keys()) if isinstance(inner_data, dict) else 'N/A'}, extracted path: {file_path}"
                )
            elif isinstance(data, str):
                # Direct string response (could be path or content)
                file_path = data
            elif isinstance(data, bytes):
                # Direct bytes response
                return data, None

            # Read file from the path
            if file_path and isinstance(file_path, str):
                path_obj = Path(file_path)

                # Check if it's a valid file path (absolute or in .composio directory)
                if path_obj.is_absolute() or ".composio" in str(path_obj):
                    try:
                        if path_obj.exists():
                            content = path_obj.read_bytes()
                            logger.info(
                                f"Successfully read {len(content)} bytes from Composio file: {file_path}"
                            )
                            return content, None
                        else:
                            logger.warning(
                                f"File path from Composio does not exist: {file_path}"
                            )
                            return None, f"File not found at path: {file_path}"
                    except Exception as e:
                        logger.error(
                            f"Failed to read file from Composio path {file_path}: {e!s}"
                        )
                        return None, f"Failed to read file: {e!s}"
                else:
                    # Not a file path - might be base64 encoded content
                    try:
                        import base64

                        content = base64.b64decode(file_path)
                        return content, None
                    except Exception:
                        # Not base64, return as UTF-8 bytes
                        return file_path.encode("utf-8"), None

            # If we got here, couldn't extract file path
            if isinstance(data, dict):
                # Log full structure for debugging
                inner_data = data.get("data", {})
                logger.warning(
                    f"Could not extract file path from Composio response. "
                    f"Top keys: {list(data.keys())}, "
                    f"Inner data keys: {list(inner_data.keys()) if isinstance(inner_data, dict) else type(inner_data).__name__}, "
                    f"Full inner data: {inner_data}"
                )
                return (
                    None,
                    f"No file path in Composio response. Keys: {list(data.keys())}, inner: {list(inner_data.keys()) if isinstance(inner_data, dict) else 'N/A'}",
                )

            return None, f"Unexpected data type from Composio: {type(data).__name__}"

        except Exception as e:
            logger.error(f"Failed to get Drive file content: {e!s}")
            return None, str(e)

    async def get_file_metadata(
        self, connected_account_id: str, entity_id: str, file_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get metadata for a specific file from Google Drive.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            file_id: The ID of the file to get metadata for.

        Returns:
            Tuple of (metadata dict, error message).
        """
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_GET_FILE_METADATA",
                params={
                    "file_id": file_id,
                    "fields": "id,name,mimeType,modifiedTime,createdTime,size",
                },
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data", {})

            # Handle nested response structure
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                if isinstance(inner_data, dict):
                    # Extract metadata fields with fallbacks for camelCase/snake_case
                    metadata = {
                        "id": inner_data.get("id") or file_id,
                        "name": inner_data.get("name", ""),
                        "mimeType": inner_data.get("mimeType")
                        or inner_data.get("mime_type", ""),
                        "modifiedTime": inner_data.get("modifiedTime")
                        or inner_data.get("modified_time", ""),
                        "createdTime": inner_data.get("createdTime")
                        or inner_data.get("created_time", ""),
                        "size": inner_data.get("size", ""),
                    }
                    return metadata, None

            return None, "Could not extract metadata from response"

        except Exception as e:
            logger.error(f"Failed to get file metadata: {e!s}")
            return None, str(e)

    async def get_drive_start_page_token(
        self, connected_account_id: str, entity_id: str
    ) -> tuple[str | None, str | None]:
        """
        Get the starting page token for Google Drive change tracking.

        This token represents the current state and is used for future delta syncs.
        Per Composio docs: Use GOOGLEDRIVE_GET_CHANGES_START_PAGE_TOKEN to get initial token.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.

        Returns:
            Tuple of (start_page_token, error message).
        """
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_GET_CHANGES_START_PAGE_TOKEN",
                params={},
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data", {})
            # Handle nested response: {data: {startPageToken: ...}, successful: ...}
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                token = (
                    inner_data.get("startPageToken")
                    or inner_data.get("start_page_token")
                    or data.get("startPageToken")
                    or data.get("start_page_token")
                )
                if token:
                    logger.info(f"Got Drive start page token: {token}")
                    return token, None

            logger.warning(f"Could not extract start page token from response: {data}")
            return None, "No start page token in response"

        except Exception as e:
            logger.error(f"Failed to get Drive start page token: {e!s}")
            return None, str(e)

    async def list_drive_changes(
        self,
        connected_account_id: str,
        entity_id: str,
        page_token: str | None = None,
        page_size: int = 100,
        include_removed: bool = True,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        List changes in Google Drive since the given page token.

        Per Composio docs: GOOGLEDRIVE_LIST_CHANGES tracks modifications to files/folders.
        If pageToken is not provided, it auto-fetches the current start page token.
        Response includes nextPageToken for pagination and newStartPageToken for future syncs.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            page_token: Page token from previous sync (optional - will auto-fetch if not provided).
            page_size: Number of changes per page.
            include_removed: Whether to include removed items in the response.

        Returns:
            Tuple of (changes list, new_start_page_token, error message).
        """
        try:
            params = {
                "pageSize": min(page_size, 100),
                "includeRemoved": include_removed,
            }
            if page_token:
                params["pageToken"] = page_token

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_LIST_CHANGES",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], None, result.get("error", "Unknown error")

            data = result.get("data", {})

            # Handle nested response structure
            changes = []
            new_start_token = None

            if isinstance(data, dict):
                inner_data = data.get("data", data)
                changes = inner_data.get("changes", []) or data.get("changes", [])

                # Get the token for next sync
                # newStartPageToken is returned when all changes have been fetched
                # nextPageToken is for pagination within the current fetch
                new_start_token = (
                    inner_data.get("newStartPageToken")
                    or inner_data.get("new_start_page_token")
                    or inner_data.get("nextPageToken")
                    or inner_data.get("next_page_token")
                    or data.get("newStartPageToken")
                    or data.get("nextPageToken")
                )

            logger.info(
                f"Got {len(changes)} Drive changes, new token: {new_start_token[:20] if new_start_token else 'None'}..."
            )
            return changes, new_start_token, None

        except Exception as e:
            logger.error(f"Failed to list Drive changes: {e!s}")
            return [], None, str(e)

    # ===== Gmail specific methods =====

    async def get_gmail_messages(
        self,
        connected_account_id: str,
        entity_id: str,
        query: str = "",
        max_results: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int | None, str | None]:
        """
        List Gmail messages via Composio with pagination support.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            query: Gmail search query.
            max_results: Maximum number of messages to return per page (default: 50 to avoid payload size issues).
            page_token: Optional pagination token for next page.

        Returns:
            Tuple of (messages list, next_page_token, result_size_estimate, error message).
        """
        try:
            # Use smaller batch size to avoid 413 payload too large errors
            # Composio uses snake_case for parameters
            params = {"max_results": min(max_results, 50)}  # Reduced from 500 to 50
            if query:
                params["query"] = query  # Composio uses 'query' not 'q'
            if page_token:
                params["page_token"] = page_token

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_FETCH_EMAILS",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], None, result.get("error", "Unknown error")

            data = result.get("data", {})

            # Try different possible response structures
            messages = []
            next_token = None
            result_size_estimate = None
            if isinstance(data, dict):
                messages = (
                    data.get("messages", [])
                    or data.get("data", {}).get("messages", [])
                    or data.get("emails", [])
                )
                # Check for pagination token in various possible locations
                next_token = (
                    data.get("nextPageToken")
                    or data.get("next_page_token")
                    or data.get("data", {}).get("nextPageToken")
                    or data.get("data", {}).get("next_page_token")
                )
                # Extract resultSizeEstimate if available (Gmail API provides this)
                result_size_estimate = (
                    data.get("resultSizeEstimate")
                    or data.get("result_size_estimate")
                    or data.get("data", {}).get("resultSizeEstimate")
                    or data.get("data", {}).get("result_size_estimate")
                )
            elif isinstance(data, list):
                messages = data

            return messages, next_token, result_size_estimate, None

        except Exception as e:
            logger.error(f"Failed to list Gmail messages: {e!s}")
            return [], None, str(e)

    async def get_gmail_message_detail(
        self, connected_account_id: str, entity_id: str, message_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get full details of a Gmail message via Composio.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            message_id: Gmail message ID.

        Returns:
            Tuple of (message details, error message).
        """
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_GET_MESSAGE_BY_MESSAGE_ID",
                params={"message_id": message_id},  # snake_case
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            return result.get("data"), None

        except Exception as e:
            logger.error(f"Failed to get Gmail message detail: {e!s}")
            return None, str(e)

    # ===== Google Calendar specific methods =====

    async def get_calendar_events(
        self,
        connected_account_id: str,
        entity_id: str,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 250,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        List Google Calendar events via Composio.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            time_min: Start time (RFC3339 format).
            time_max: End time (RFC3339 format).
            max_results: Maximum number of events.

        Returns:
            Tuple of (events list, error message).
        """
        try:
            # Composio uses snake_case for parameters
            params = {
                "max_results": min(max_results, 250),
                "single_events": True,
                "order_by": "startTime",
            }
            if time_min:
                params["time_min"] = time_min
            if time_max:
                params["time_max"] = time_max

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLECALENDAR_EVENTS_LIST",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], result.get("error", "Unknown error")

            data = result.get("data", {})

            # Try different possible response structures
            events = []
            if isinstance(data, dict):
                events = (
                    data.get("items", [])
                    or data.get("data", {}).get("items", [])
                    or data.get("events", [])
                )
            elif isinstance(data, list):
                events = data

            return events, None

        except Exception as e:
            logger.error(f"Failed to list Calendar events: {e!s}")
            return [], str(e)

    # ===== User Info Methods =====

    async def get_connected_account_email(
        self,
        connected_account_id: str,
        entity_id: str,
        toolkit_id: str,
    ) -> str | None:
        """
        Get the email address associated with a connected account.

        Uses toolkit-specific API calls:
        - Google Drive: List files and extract owner email
        - Gmail: Get user profile
        - Google Calendar: List events and extract organizer/creator email

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            toolkit_id: The toolkit identifier (googledrive, gmail, googlecalendar).

        Returns:
            Email address string or None if not available.
        """
        try:
            email = await self._extract_email_for_toolkit(
                connected_account_id, entity_id, toolkit_id
            )

            if email:
                logger.info(f"Retrieved email {email} for {toolkit_id} connector")
            else:
                logger.warning(f"Could not retrieve email for {toolkit_id} connector")

            return email

        except Exception as e:
            logger.error(f"Failed to get email for {toolkit_id} connector: {e!s}")
            return None

    async def _extract_email_for_toolkit(
        self,
        connected_account_id: str,
        entity_id: str,
        toolkit_id: str,
    ) -> str | None:
        """Extract email based on toolkit type."""
        if toolkit_id == "googledrive":
            return await self._get_drive_owner_email(connected_account_id, entity_id)
        elif toolkit_id == "gmail":
            return await self._get_gmail_profile_email(connected_account_id, entity_id)
        elif toolkit_id == "googlecalendar":
            return await self._get_calendar_user_email(connected_account_id, entity_id)
        return None

    async def _get_drive_owner_email(
        self, connected_account_id: str, entity_id: str
    ) -> str | None:
        """Get email from Google Drive file owner where me=True."""
        # List files owned by the user and find one where owner.me=True
        result = await self.execute_tool(
            connected_account_id=connected_account_id,
            tool_name="GOOGLEDRIVE_LIST_FILES",
            params={
                "page_size": 10,
                "fields": "files(owners)",
                "q": "'me' in owners",  # Only files owned by current user
            },
            entity_id=entity_id,
        )

        if not result.get("success"):
            return None

        data = result.get("data", {})
        if not isinstance(data, dict):
            return None

        files = data.get("files") or data.get("data", {}).get("files", [])
        for file in files:
            owners = file.get("owners", [])
            for owner in owners:
                # Only return email if this is the current user (me=True)
                if owner.get("me") and owner.get("emailAddress"):
                    return owner.get("emailAddress")

        return None

    async def _get_gmail_profile_email(
        self, connected_account_id: str, entity_id: str
    ) -> str | None:
        """Get email from Gmail profile."""
        result = await self.execute_tool(
            connected_account_id=connected_account_id,
            tool_name="GMAIL_GET_PROFILE",
            params={},
            entity_id=entity_id,
        )

        if not result.get("success"):
            return None

        data = result.get("data", {})
        if not isinstance(data, dict):
            return None

        return data.get("emailAddress") or data.get("data", {}).get("emailAddress")

    async def _get_calendar_user_email(
        self, connected_account_id: str, entity_id: str
    ) -> str | None:
        """Get email from Google Calendar primary calendar or event organizer/creator."""
        # Method 1: Get primary calendar - the "summary" field is the user's email
        result = await self.execute_tool(
            connected_account_id=connected_account_id,
            tool_name="GOOGLECALENDAR_GET_CALENDAR",
            params={"calendar_id": "primary"},
            entity_id=entity_id,
        )

        if result.get("success"):
            data = result.get("data", {})
            if isinstance(data, dict):
                # Handle nested structure: data['data']['calendar_data']['summary']
                calendar_data = (
                    data.get("data", {}).get("calendar_data", {})
                    if isinstance(data.get("data"), dict)
                    else {}
                )
                summary = (
                    calendar_data.get("summary")
                    or calendar_data.get("id")
                    or data.get("data", {}).get("summary")
                    or data.get("summary")
                )
                if summary and "@" in summary:
                    return summary

        # Method 2: Fallback - list events to get calendar summary (owner's email)
        result = await self.execute_tool(
            connected_account_id=connected_account_id,
            tool_name="GOOGLECALENDAR_EVENTS_LIST",
            params={"max_results": 20},
            entity_id=entity_id,
        )

        if not result.get("success"):
            return None

        data = result.get("data", {})
        if not isinstance(data, dict):
            return None

        # The events list response contains 'summary' which is the calendar owner's email
        nested_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        summary = nested_data.get("summary") or data.get("summary")
        if summary and "@" in summary:
            return summary

        # Method 3: Check event organizers/creators
        items = nested_data.get("items", []) or data.get("items", [])
        for event in items:
            organizer = event.get("organizer", {})
            if organizer.get("self"):
                return organizer.get("email")

            creator = event.get("creator", {})
            if creator.get("self"):
                return creator.get("email")

        return None


# Singleton instance
_composio_service: ComposioService | None = None


def get_composio_service() -> ComposioService:
    """
    Get or create the Composio service singleton.

    Returns:
        ComposioService instance.

    Raises:
        ValueError: If Composio is not properly configured.
    """
    global _composio_service
    if _composio_service is None:
        _composio_service = ComposioService()
    return _composio_service
