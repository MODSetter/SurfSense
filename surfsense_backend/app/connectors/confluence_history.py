"""
Confluence OAuth Connector.

Handles OAuth-based authentication and token refresh for Confluence API access.
"""

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.connectors.confluence_connector import ConfluenceConnector
from app.db import SearchSourceConnector
from app.routes.confluence_add_connector_route import refresh_confluence_token
from app.schemas.atlassian_auth_credentials import AtlassianAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class ConfluenceHistoryConnector:
    """
    Confluence connector with OAuth support and automatic token refresh.

    This connector uses OAuth 2.0 access tokens to authenticate with the
    Confluence API. It automatically refreshes expired tokens when needed.
    Also supports legacy API token authentication for backward compatibility.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: AtlassianAuthCredentialsBase | None = None,
    ):
        """
        Initialize the ConfluenceHistoryConnector with auto-refresh capability.

        Args:
            session: Database session for updating connector
            connector_id: Connector ID for direct updates
            credentials: Confluence OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._cloud_id: str | None = None
        self._base_url: str | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._use_oauth = True
        self._legacy_email: str | None = None
        self._legacy_api_token: str | None = None
        self._legacy_confluence_client: ConfluenceConnector | None = None

    async def _get_valid_token(self) -> str:
        """
        Get valid Confluence access token, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # Load credentials from DB if not provided
        if self._credentials is None:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            connector = result.scalars().first()

            if not connector:
                raise ValueError(f"Connector {self._connector_id} not found")

            config_data = connector.config.copy()

            # Check if using OAuth or legacy API token
            is_oauth = config_data.get("_token_encrypted", False) or config_data.get(
                "access_token"
            )

            if is_oauth:
                # OAuth 2.0 authentication
                # Decrypt credentials if they are encrypted
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    try:
                        token_encryption = TokenEncryption(config.SECRET_KEY)

                        # Decrypt sensitive fields
                        if config_data.get("access_token"):
                            config_data["access_token"] = (
                                token_encryption.decrypt_token(
                                    config_data["access_token"]
                                )
                            )
                        if config_data.get("refresh_token"):
                            config_data["refresh_token"] = (
                                token_encryption.decrypt_token(
                                    config_data["refresh_token"]
                                )
                            )

                        logger.info(
                            f"Decrypted Confluence credentials for connector {self._connector_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to decrypt Confluence credentials for connector {self._connector_id}: {e!s}"
                        )
                        raise ValueError(
                            f"Failed to decrypt Confluence credentials: {e!s}"
                        ) from e

                try:
                    self._credentials = AtlassianAuthCredentialsBase.from_dict(
                        config_data
                    )
                    # Store cloud_id and base_url for API calls (with backward compatibility for site_url)
                    self._cloud_id = config_data.get("cloud_id")
                    self._base_url = config_data.get("base_url") or config_data.get(
                        "site_url"
                    )
                    self._use_oauth = True
                except Exception as e:
                    raise ValueError(
                        f"Invalid Confluence OAuth credentials: {e!s}"
                    ) from e
            else:
                # Legacy API token authentication
                self._legacy_email = config_data.get("CONFLUENCE_EMAIL")
                self._legacy_api_token = config_data.get("CONFLUENCE_API_TOKEN")
                self._base_url = config_data.get("CONFLUENCE_BASE_URL")
                self._use_oauth = False

                if (
                    not self._legacy_email
                    or not self._legacy_api_token
                    or not self._base_url
                ):
                    raise ValueError(
                        "Confluence credentials not found in connector config"
                    )

        # Check if token is expired and refreshable (only for OAuth)
        if (
            self._use_oauth
            and self._credentials.is_expired
            and self._credentials.is_refreshable
        ):
            try:
                logger.info(
                    f"Confluence token expired for connector {self._connector_id}, refreshing..."
                )

                # Get connector for refresh
                result = await self._session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == self._connector_id
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    raise RuntimeError(
                        f"Connector {self._connector_id} not found; cannot refresh token."
                    )

                # Refresh token
                connector = await refresh_confluence_token(self._session, connector)

                # Reload credentials after refresh
                config_data = connector.config.copy()
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                self._credentials = AtlassianAuthCredentialsBase.from_dict(config_data)
                self._cloud_id = config_data.get("cloud_id")
                # Handle backward compatibility: check both base_url and site_url
                self._base_url = config_data.get("base_url") or config_data.get(
                    "site_url"
                )

                # Invalidate cached client so it's recreated with new token
                if self._http_client:
                    await self._http_client.aclose()
                    self._http_client = None

                logger.info(
                    f"Successfully refreshed Confluence token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Confluence token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Confluence OAuth credentials: {e!s}"
                ) from e

        if self._use_oauth:
            return self._credentials.access_token
        else:
            # For legacy auth, return empty string (not used for token-based auth)
            return ""

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client with valid token.

        Returns:
            httpx.AsyncClient instance
        """
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _get_legacy_client(self) -> ConfluenceConnector:
        """
        Get or create ConfluenceConnector with legacy credentials.

        Returns:
            ConfluenceConnector instance
        """
        if self._legacy_confluence_client is None:
            self._legacy_confluence_client = ConfluenceConnector(
                base_url=self._base_url,
                email=self._legacy_email,
                api_token=self._legacy_api_token,
            )
        return self._legacy_confluence_client

    async def _get_base_url(self) -> str:
        """
        Get the base URL for Confluence API calls.

        Returns:
            Base URL string
        """
        if not self._use_oauth:
            # For legacy auth, use the base_url directly
            return self._base_url or ""

        if not self._cloud_id:
            raise ValueError("Cloud ID not available. Cannot construct API URL.")

        # Use the Atlassian API format: https://api.atlassian.com/ex/confluence/{cloudid}
        return f"https://api.atlassian.com/ex/confluence/{self._cloud_id}"

    async def _make_api_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a request to the Confluence API.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters for the request (optional)

        Returns:
            Response data from the API

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        if not self._use_oauth:
            # Use legacy ConfluenceConnector for API requests
            client = await self._get_legacy_client()
            # ConfluenceConnector uses synchronous requests, so we need to handle this differently
            # For now, we'll use the legacy client's make_api_request method
            # But since it's sync, we'll need to wrap it
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, client.make_api_request, endpoint, params
            )

        # OAuth flow
        token = await self._get_valid_token()
        base_url = await self._get_base_url()
        http_client = await self._get_client()

        url = f"{base_url}/wiki/api/v2/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            response = await http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Enhanced error logging to see the actual error
            error_detail = {
                "status_code": e.response.status_code,
                "url": str(e.request.url),
                "response_text": e.response.text,
                "headers": dict(e.response.headers),
            }
            logger.error(f"Confluence API HTTP error: {error_detail}")
            raise Exception(
                f"Confluence API request failed (HTTP {e.response.status_code}): {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Confluence API request error: {e!s}", exc_info=True)
            raise Exception(f"Confluence API request failed: {e!s}") from e

    async def get_all_spaces(self) -> list[dict[str, Any]]:
        """
        Fetch all spaces from Confluence.

        Returns:
            List of space objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        params = {
            "limit": 100,
        }

        all_spaces = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            result = await self._make_api_request("spaces", params)

            if not isinstance(result, dict) or "results" not in result:
                raise Exception("Invalid response from Confluence API")

            spaces = result["results"]
            all_spaces.extend(spaces)

            # Check if there are more spaces to fetch
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next link if available
            next_link = links["next"]
            if "cursor=" in next_link:
                cursor = next_link.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_spaces

    async def get_pages_in_space(
        self, space_id: str, include_body: bool = True
    ) -> list[dict[str, Any]]:
        """
        Fetch all pages in a specific space.

        Args:
            space_id: The ID of the space to fetch pages from
            include_body: Whether to include page body content

        Returns:
            List of page objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        params = {
            "limit": 100,
        }

        if include_body:
            params["body-format"] = "storage"

        all_pages = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            result = await self._make_api_request(f"spaces/{space_id}/pages", params)

            if not isinstance(result, dict) or "results" not in result:
                raise Exception("Invalid response from Confluence API")

            pages = result["results"]
            all_pages.extend(pages)

            # Check if there are more pages to fetch
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next link if available
            next_link = links["next"]
            if "cursor=" in next_link:
                cursor = next_link.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_pages

    async def get_page_comments(self, page_id: str) -> list[dict[str, Any]]:
        """
        Fetch all comments for a specific page (both footer and inline comments).

        Args:
            page_id: The ID of the page to fetch comments from

        Returns:
            List of comment objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        all_comments = []

        # Get footer comments
        footer_comments = await self._get_comments_for_page(page_id, "footer-comments")
        all_comments.extend(footer_comments)

        # Get inline comments
        inline_comments = await self._get_comments_for_page(page_id, "inline-comments")
        all_comments.extend(inline_comments)

        return all_comments

    async def _get_comments_for_page(
        self, page_id: str, comment_type: str
    ) -> list[dict[str, Any]]:
        """
        Helper method to fetch comments of a specific type for a page.

        Args:
            page_id: The ID of the page
            comment_type: Type of comments ('footer-comments' or 'inline-comments')

        Returns:
            List of comment objects
        """
        params = {
            "limit": 100,
            "body-format": "storage",
        }

        all_comments = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            result = await self._make_api_request(
                f"pages/{page_id}/{comment_type}", params
            )

            if not isinstance(result, dict) or "results" not in result:
                break  # No comments or invalid response

            comments = result["results"]
            all_comments.extend(comments)

            # Check if there are more comments to fetch
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next link if available
            next_link = links["next"]
            if "cursor=" in next_link:
                cursor = next_link.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_comments

    async def get_pages_by_date_range(
        self,
        start_date: str,
        end_date: str,
        space_ids: list[str] | None = None,
        include_comments: bool = True,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch pages within a date range, optionally filtered by spaces.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            space_ids: Optional list of space IDs to filter pages
            include_comments: Whether to include comments for each page

        Returns:
            Tuple containing (pages list with comments, error message or None)
        """
        try:
            if not self._use_oauth:
                # Use legacy ConfluenceConnector for API requests
                client = await self._get_legacy_client()
                # Ensure credentials are loaded
                await self._get_valid_token()
                # ConfluenceConnector.get_pages_by_date_range is synchronous
                import asyncio

                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    client.get_pages_by_date_range,
                    start_date,
                    end_date,
                    space_ids,
                    include_comments,
                )

            # OAuth flow
            all_pages = []

            if space_ids:
                # Fetch pages from specific spaces
                for space_id in space_ids:
                    pages = await self.get_pages_in_space(space_id, include_body=True)
                    all_pages.extend(pages)
            else:
                # Fetch all pages (this might be expensive for large instances)
                params = {
                    "limit": 100,
                    "body-format": "storage",
                }

                cursor = None
                while True:
                    if cursor:
                        params["cursor"] = cursor

                    result = await self._make_api_request("pages", params)
                    if not isinstance(result, dict) or "results" not in result:
                        break

                    pages = result["results"]
                    all_pages.extend(pages)

                    links = result.get("_links", {})
                    if "next" not in links:
                        break

                    next_link = links["next"]
                    if "cursor=" in next_link:
                        cursor = next_link.split("cursor=")[1].split("&")[0]
                    else:
                        break

            return all_pages, None

        except Exception as e:
            return [], f"Error fetching pages: {e!s}"

    async def close(self):
        """Close the HTTP client connection."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        # Legacy client doesn't need explicit closing
        self._legacy_confluence_client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
