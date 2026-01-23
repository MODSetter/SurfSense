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


# Mapping of toolkit IDs to their Composio auth config IDs
# These use Composio's managed OAuth (no custom credentials needed)
COMPOSIO_TOOLKIT_AUTH_CONFIGS = {
    "googledrive": "default",  # Uses Composio's managed Google OAuth
    "gmail": "default",
    "googlecalendar": "default",
    "slack": "default",
    "notion": "default",
    "github": "default",
}

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


class ComposioService:
    """Service for interacting with Composio API."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize the Composio service.

        Args:
            api_key: Composio API key. If not provided, uses config.COMPOSIO_API_KEY.
        """
        self.api_key = api_key or config.COMPOSIO_API_KEY
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY is required but not configured")
        self.client = Composio(api_key=self.api_key)

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

    async def get_connected_account(
        self, connected_account_id: str
    ) -> dict[str, Any] | None:
        """
        Get details of a connected account.

        Args:
            connected_account_id: The Composio connected account ID.

        Returns:
            Connected account details or None if not found.
        """
        try:
            # Pass connected_account_id as positional argument (not keyword)
            account = self.client.connected_accounts.get(connected_account_id)
            return {
                "id": account.id,
                "status": getattr(account, "status", None),
                "toolkit": getattr(account, "toolkit", None),
                "user_id": getattr(account, "user_id", None),
            }
        except Exception as e:
            logger.error(
                f"Failed to get connected account {connected_account_id}: {e!s}"
            )
            return None

    async def list_all_connections(self) -> list[dict[str, Any]]:
        """
        List ALL connected accounts (for debugging).

        Returns:
            List of all connected account details.
        """
        try:
            accounts_response = self.client.connected_accounts.list()

            if hasattr(accounts_response, "items"):
                accounts = accounts_response.items
            elif hasattr(accounts_response, "__iter__"):
                accounts = accounts_response
            else:
                logger.warning(
                    f"Unexpected accounts response type: {type(accounts_response)}"
                )
                return []

            result = []
            for acc in accounts:
                toolkit_raw = getattr(acc, "toolkit", None)
                toolkit_info = None
                if toolkit_raw:
                    if isinstance(toolkit_raw, str):
                        toolkit_info = toolkit_raw
                    elif hasattr(toolkit_raw, "slug"):
                        toolkit_info = toolkit_raw.slug
                    elif hasattr(toolkit_raw, "name"):
                        toolkit_info = toolkit_raw.name
                    else:
                        toolkit_info = str(toolkit_raw)

                result.append(
                    {
                        "id": acc.id,
                        "status": getattr(acc, "status", None),
                        "toolkit": toolkit_info,
                        "user_id": getattr(acc, "user_id", None),
                    }
                )

            logger.info(f"DEBUG: Found {len(result)} TOTAL connections in Composio")
            return result
        except Exception as e:
            logger.error(f"Failed to list all connections: {e!s}")
            return []

    async def list_user_connections(self, user_id: str) -> list[dict[str, Any]]:
        """
        List all connected accounts for a user.

        Args:
            user_id: The user's unique identifier.

        Returns:
            List of connected account details.
        """
        try:
            logger.info(f"DEBUG: Calling connected_accounts.list(user_id='{user_id}')")
            accounts_response = self.client.connected_accounts.list(user_id=user_id)

            # Handle paginated response (may have .items attribute) or direct list
            if hasattr(accounts_response, "items"):
                accounts = accounts_response.items
            elif hasattr(accounts_response, "__iter__"):
                accounts = accounts_response
            else:
                logger.warning(
                    f"Unexpected accounts response type: {type(accounts_response)}"
                )
                return []

            result = []
            for acc in accounts:
                # Extract toolkit info - might be string or object
                toolkit_raw = getattr(acc, "toolkit", None)
                toolkit_info = None
                if toolkit_raw:
                    if isinstance(toolkit_raw, str):
                        toolkit_info = toolkit_raw
                    elif hasattr(toolkit_raw, "slug"):
                        toolkit_info = toolkit_raw.slug
                    elif hasattr(toolkit_raw, "name"):
                        toolkit_info = toolkit_raw.name
                    else:
                        toolkit_info = toolkit_raw

                result.append(
                    {
                        "id": acc.id,
                        "status": getattr(acc, "status", None),
                        "toolkit": toolkit_info,
                    }
                )

            logger.info(f"Found {len(result)} connections for user {user_id}: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to list connections for user {user_id}: {e!s}")
            return []

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
            logger.info(f"DEBUG: Executing tool {tool_name} with params: {params}")
            result = self.client.tools.execute(
                slug=tool_name,
                connected_account_id=connected_account_id,
                user_id=entity_id,  # SDK expects user_id parameter
                arguments=params or {},
                dangerously_skip_version_check=True,
            )
            logger.info(f"DEBUG: Tool {tool_name} raw result type: {type(result)}")
            logger.info(f"DEBUG: Tool {tool_name} raw result: {result}")
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
            params = {
                "page_size": min(page_size, 100),
            }
            if folder_id:
                params["folder_id"] = folder_id
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
            logger.info(
                f"DEBUG: Drive data type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}"
            )

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

            logger.info(f"DEBUG: Extracted {len(files)} drive files")
            return files, next_token, None

        except Exception as e:
            logger.error(f"Failed to list Drive files: {e!s}")
            return [], None, str(e)

    async def get_drive_file_content(
        self, connected_account_id: str, entity_id: str, file_id: str
    ) -> tuple[bytes | None, str | None]:
        """
        Download file content from Google Drive via Composio.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            file_id: Google Drive file ID.

        Returns:
            Tuple of (file content bytes, error message).
        """
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLEDRIVE_DOWNLOAD_FILE",
                params={"file_id": file_id},  # snake_case
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            content = result.get("data")
            if isinstance(content, str):
                content = content.encode("utf-8")

            return content, None

        except Exception as e:
            logger.error(f"Failed to get Drive file content: {e!s}")
            return None, str(e)

    # ===== Gmail specific methods =====

    async def get_gmail_messages(
        self,
        connected_account_id: str,
        entity_id: str,
        query: str = "",
        max_results: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        List Gmail messages via Composio.

        Args:
            connected_account_id: Composio connected account ID.
            entity_id: The entity/user ID that owns the connected account.
            query: Gmail search query.
            max_results: Maximum number of messages to return.

        Returns:
            Tuple of (messages list, error message).
        """
        try:
            # Composio uses snake_case for parameters, max is 500
            params = {"max_results": min(max_results, 500)}
            if query:
                params["query"] = query  # Composio uses 'query' not 'q'

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_FETCH_EMAILS",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], result.get("error", "Unknown error")

            data = result.get("data", {})
            logger.info(
                f"DEBUG: Gmail data type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}"
            )
            logger.info(f"DEBUG: Gmail full data: {data}")

            # Try different possible response structures
            messages = []
            if isinstance(data, dict):
                messages = (
                    data.get("messages", [])
                    or data.get("data", {}).get("messages", [])
                    or data.get("emails", [])
                )
            elif isinstance(data, list):
                messages = data

            logger.info(f"DEBUG: Extracted {len(messages)} messages")
            return messages, None

        except Exception as e:
            logger.error(f"Failed to list Gmail messages: {e!s}")
            return [], str(e)

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
            logger.info(
                f"DEBUG: Calendar data type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}"
            )
            logger.info(f"DEBUG: Calendar full data: {data}")

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

            logger.info(f"DEBUG: Extracted {len(events)} calendar events")
            return events, None

        except Exception as e:
            logger.error(f"Failed to list Calendar events: {e!s}")
            return [], str(e)


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
