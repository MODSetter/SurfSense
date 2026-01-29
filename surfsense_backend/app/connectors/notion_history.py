import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from notion_client import AsyncClient
from notion_client.errors import APIResponseError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector
from app.routes.notion_add_connector_route import refresh_notion_token
from app.schemas.notion_auth_credentials import NotionAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar("T")

# ============================================================================
# Retry Configuration (per Notion API docs)
# https://developers.notion.com/reference/request-limits
# https://developers.notion.com/reference/status-codes
# ============================================================================
MAX_RETRIES = 5
BASE_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds (Notion's max request timeout)

# Type alias for retry callback function
# Signature: async callback(retry_reason, attempt, max_attempts, wait_seconds) -> None
# retry_reason: 'rate_limit', 'server_error', 'timeout'
# This callback can be used to update notifications during retries
RetryCallbackType = Callable[[str, int, int, float], Awaitable[None]]

# HTTP status codes that should trigger a retry
# 429: rate_limited - Use Retry-After header
# 500: internal_server_error - Unexpected error
# 502: bad_gateway - Failed upstream connection
# 503: service_unavailable - Notion unavailable or timeout
# 504: gateway_timeout - Notion timed out
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Known unsupported block types that Notion API doesn't expose
# These will be skipped gracefully instead of failing the entire sync
UNSUPPORTED_BLOCK_TYPE_ERRORS = [
    "transcription is not supported",
    "ai_block is not supported",
    "is not supported via the API",
]

# Known unsupported block types to check before API calls
UNSUPPORTED_BLOCK_TYPES = ["transcription", "ai_block"]


class NotionHistoryConnector:
    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: NotionAuthCredentialsBase | None = None,
    ):
        """
        Initialize the NotionHistoryConnector with auto-refresh capability.

        Args:
            session: Database session for updating connector
            connector_id: Connector ID for direct updates
            credentials: Notion OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._notion_client: AsyncClient | None = None
        # Track pages with skipped unsupported content (for user notifications)
        self._pages_with_skipped_content: list[str] = []
        # Optional callback to notify about retry progress (for user notifications)
        self._on_retry_callback: RetryCallbackType | None = None
        # Track if using legacy integration token (for upgrade notification)
        self._using_legacy_token: bool = False

    def set_retry_callback(self, callback: RetryCallbackType | None) -> None:
        """
        Set a callback function to be called when API calls are retried.

        This allows the indexer to receive notifications about rate limits
        and other transient errors, which can be used to update user-facing
        notifications.

        Args:
            callback: Async function with signature:
                      callback(retry_reason, attempt, max_attempts, wait_seconds) -> None
                      retry_reason: 'rate_limit', 'server_error', or 'timeout'
                      Set to None to disable callbacks.
        """
        self._on_retry_callback = callback

    async def _get_valid_token(self) -> str:
        """
        Get valid Notion access token, refreshing if needed.

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

            # Check for legacy integration token format first
            # (for connectors created before OAuth was implemented)
            legacy_token = config_data.get("NOTION_INTEGRATION_TOKEN")
            raw_access_token = config_data.get("access_token")

            # Validate that we have some form of token
            if not raw_access_token and not legacy_token:
                raise ValueError(
                    "Notion integration not properly connected. "
                    "Please remove and re-add the Notion connector."
                )

            # Decrypt credentials if they are encrypted
            token_encrypted = config_data.get("_token_encrypted", False)
            if token_encrypted and config.SECRET_KEY:
                try:
                    token_encryption = TokenEncryption(config.SECRET_KEY)

                    # Decrypt sensitive fields
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                    logger.info(
                        f"Decrypted Notion credentials for connector {self._connector_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt Notion credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        "Notion credentials could not be decrypted. "
                        "Please remove and re-add the Notion connector."
                    ) from e

            # Handle legacy format: convert NOTION_INTEGRATION_TOKEN to access_token
            if not config_data.get("access_token") and legacy_token:
                config_data["access_token"] = legacy_token
                self._using_legacy_token = True
                logger.info(
                    f"Using legacy NOTION_INTEGRATION_TOKEN for connector {self._connector_id}"
                )

            # Final validation: ensure we have a valid access_token after all processing
            final_token = config_data.get("access_token")
            if not final_token or (
                isinstance(final_token, str) and not final_token.strip()
            ):
                raise ValueError(
                    "Notion access token is invalid or empty. "
                    "Please remove and re-add the Notion connector."
                )

            try:
                self._credentials = NotionAuthCredentialsBase.from_dict(config_data)
            except KeyError as e:
                raise ValueError(
                    f"Notion credentials are incomplete (missing {e}). "
                    "Please reconnect your Notion account."
                ) from e
            except Exception as e:
                raise ValueError(
                    f"Notion credentials format error: {e!s}. "
                    "Please reconnect your Notion account."
                ) from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    f"Notion token expired for connector {self._connector_id}, refreshing..."
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
                connector = await refresh_notion_token(self._session, connector)

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

                self._credentials = NotionAuthCredentialsBase.from_dict(config_data)

                # Invalidate cached client so it's recreated with new token
                self._notion_client = None

                logger.info(
                    f"Successfully refreshed Notion token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Notion token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Notion OAuth credentials: {e!s}"
                ) from e

        return self._credentials.access_token

    async def _get_client(self) -> AsyncClient:
        """
        Get or create Notion AsyncClient with valid token.

        Returns:
            Notion AsyncClient instance
        """
        if self._notion_client is None:
            token = await self._get_valid_token()
            self._notion_client = AsyncClient(auth=token)
        return self._notion_client

    async def _api_call_with_retry(
        self,
        api_func: Callable[..., Awaitable[T]],
        *args: Any,
        on_retry: RetryCallbackType | None = None,
        **kwargs: Any,
    ) -> T:
        """
        Execute Notion API call with retry logic and exponential backoff.

        Handles retryable errors per Notion API documentation:
        - 429 rate_limited: Uses Retry-After header value
        - 500 internal_server_error: Retries with exponential backoff
        - 502 bad_gateway: Retries with exponential backoff
        - 503 service_unavailable: Retries with exponential backoff
        - 504 gateway_timeout: Retries with exponential backoff

        Args:
            api_func: The async Notion API function to call
            *args: Positional arguments to pass to the API function
            on_retry: Optional callback to notify about retry progress.
                      Signature: async callback(retry_reason, attempt, max_attempts, wait_seconds)
                      retry_reason is one of: 'rate_limit', 'server_error', 'timeout'
            **kwargs: Keyword arguments to pass to the API function

        Returns:
            The result from the API call

        Raises:
            APIResponseError: If all retries are exhausted or error is not retryable
        """
        last_exception: APIResponseError | None = None
        retry_delay = BASE_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                return await api_func(*args, **kwargs)

            except APIResponseError as e:
                last_exception = e

                # Check if this error is retryable
                if e.status not in RETRYABLE_STATUS_CODES:
                    # Not retryable (e.g., 400, 401, 403, 404) - raise immediately
                    raise

                # Check if we've exhausted retries
                if attempt == MAX_RETRIES - 1:
                    logger.error(
                        f"Notion API call failed after {MAX_RETRIES} retries. "
                        f"Last error: {e.status} {e.code}"
                    )
                    raise

                # Determine retry reason and wait time based on status code
                if e.status == 429:
                    # Rate limited - use Retry-After header if available
                    retry_reason = "rate_limit"
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                        except (ValueError, TypeError):
                            wait_time = retry_delay
                    else:
                        wait_time = retry_delay
                    logger.warning(
                        f"Notion API rate limited (429). "
                        f"Waiting {wait_time}s. Attempt {attempt + 1}/{MAX_RETRIES}"
                    )
                elif e.status == 504:
                    # Gateway timeout
                    retry_reason = "timeout"
                    wait_time = min(retry_delay, MAX_RETRY_DELAY)
                    logger.warning(
                        f"Notion API timeout ({e.status}). "
                        f"Retrying in {wait_time}s. Attempt {attempt + 1}/{MAX_RETRIES}"
                    )
                else:
                    # Server error (500/502/503) - use exponential backoff
                    retry_reason = "server_error"
                    wait_time = min(retry_delay, MAX_RETRY_DELAY)
                    logger.warning(
                        f"Notion API error {e.status} ({e.code}). "
                        f"Retrying in {wait_time}s. Attempt {attempt + 1}/{MAX_RETRIES}"
                    )

                # Notify about retry via callback (for user notifications)
                # Call before sleeping so user sees the message while we wait
                if on_retry:
                    try:
                        await on_retry(
                            retry_reason,
                            attempt + 1,  # 1-based for display
                            MAX_RETRIES,
                            wait_time,
                        )
                    except Exception as callback_error:
                        # Don't let callback errors break the retry logic
                        logger.warning(f"Retry callback failed: {callback_error}")

                # Wait before retrying
                await asyncio.sleep(wait_time)

                # Exponential backoff for next attempt
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in retry logic")

    async def close(self):
        """Close the async client connection."""
        if self._notion_client:
            await self._notion_client.aclose()
            self._notion_client = None

    def get_pages_with_skipped_content(self) -> list[str]:
        """
        Get list of page titles that had unsupported content skipped.

        Returns:
            List of page titles with skipped content
        """
        return self._pages_with_skipped_content

    def get_skipped_content_count(self) -> int:
        """
        Get count of pages that had unsupported content skipped.

        Returns:
            Number of pages with skipped content
        """
        return len(self._pages_with_skipped_content)

    def is_using_legacy_token(self) -> bool:
        """
        Check if connector is using legacy integration token format.

        Returns:
            True if using legacy NOTION_INTEGRATION_TOKEN, False if using OAuth
        """
        return self._using_legacy_token

    def _record_skipped_content(self, page_title: str):
        """
        Record that a page had unsupported content skipped.

        Args:
            page_title: Title of the page with skipped content
        """
        if page_title not in self._pages_with_skipped_content:
            self._pages_with_skipped_content.append(page_title)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_all_pages(self, start_date=None, end_date=None):
        """
        Fetches all pages shared with your integration and their content.

        Args:
            start_date (str, optional): ISO 8601 date string (e.g., "2023-01-01T00:00:00Z")
            end_date (str, optional): ISO 8601 date string (e.g., "2023-12-31T23:59:59Z")

        Returns:
            list: List of dictionaries containing page data
        """
        notion = await self._get_client()

        # Build the filter for the search
        # Note: Notion API requires specific filter structure
        search_params: dict[str, Any] = {}

        # Filter for pages only (not databases)
        search_params["filter"] = {"value": "page", "property": "object"}

        # Add date filters if provided
        if start_date or end_date:
            date_filter = {}

            if start_date:
                date_filter["on_or_after"] = start_date

            if end_date:
                date_filter["on_or_before"] = end_date

            # Add the date filter to the search params
            if date_filter:
                search_params["sort"] = {
                    "direction": "descending",
                    "timestamp": "last_edited_time",
                }

        # Paginate through all pages the integration has access to
        pages = []
        has_more = True
        cursor = None

        while has_more:
            try:
                if cursor:
                    search_params["start_cursor"] = cursor

                # Use retry wrapper for search API call
                search_results = await self._api_call_with_retry(
                    notion.search, on_retry=self._on_retry_callback, **search_params
                )

                pages.extend(search_results["results"])
                has_more = search_results.get("has_more", False)

                if has_more:
                    cursor = search_results.get("next_cursor")

            except APIResponseError as e:
                error_message = str(e)
                # Handle invalid cursor - stop pagination gracefully
                if "start_cursor provided is invalid" in error_message:
                    logger.warning(
                        f"Invalid pagination cursor encountered. "
                        f"Continuing with {len(pages)} pages already fetched."
                    )
                    has_more = False
                    continue
                # Re-raise other errors
                raise

        all_page_data = []

        for page in pages:
            page_id = page["id"]
            page_title = self.get_page_title(page)

            # Get detailed page information (pass title for skip tracking)
            page_content, had_skipped_content = await self.get_page_content(
                page_id, page_title
            )

            # Record if this page had skipped content
            if had_skipped_content:
                self._record_skipped_content(page_title)

            all_page_data.append(
                {
                    "page_id": page_id,
                    "title": page_title,
                    "content": page_content,
                }
            )

        return all_page_data

    def get_page_title(self, page):
        """
        Extracts the title from a page object.

        Args:
            page (dict): Notion page object

        Returns:
            str: Page title or a fallback string
        """
        # Title can be in different properties depending on the page type
        if "properties" in page:
            # Try to find a title property
            for _prop_name, prop_data in page["properties"].items():
                if prop_data["type"] == "title" and len(prop_data["title"]) > 0:
                    return " ".join(
                        [text_obj["plain_text"] for text_obj in prop_data["title"]]
                    )

        # If no title found, return the page ID as fallback
        return f"Untitled page ({page['id']})"

    async def get_page_content(
        self, page_id: str, page_title: str | None = None
    ) -> tuple[list, bool]:
        """
        Fetches the content (blocks) of a specific page.

        Args:
            page_id (str): The ID of the page to fetch
            page_title (str, optional): Title of the page (for logging)

        Returns:
            tuple: (List of processed blocks, bool indicating if content was skipped)
        """
        notion = await self._get_client()

        blocks = []
        has_more = True
        cursor = None
        skipped_blocks_count = 0
        had_skipped_content = False

        # Paginate through all blocks
        while has_more:
            try:
                # Use retry wrapper for blocks.children.list API call
                if cursor:
                    response = await self._api_call_with_retry(
                        notion.blocks.children.list,
                        on_retry=self._on_retry_callback,
                        block_id=page_id,
                        start_cursor=cursor,
                    )
                else:
                    response = await self._api_call_with_retry(
                        notion.blocks.children.list,
                        on_retry=self._on_retry_callback,
                        block_id=page_id,
                    )

                blocks.extend(response["results"])
                has_more = response["has_more"]

                if has_more:
                    cursor = response["next_cursor"]

            except APIResponseError as e:
                error_message = str(e)
                # Check if this is an unsupported block type error
                if any(err in error_message for err in UNSUPPORTED_BLOCK_TYPE_ERRORS):
                    logger.warning(
                        f"Skipping page blocks due to unsupported block type in page {page_id}: {error_message}"
                    )
                    skipped_blocks_count += 1
                    had_skipped_content = True
                    # If we haven't fetched any blocks yet, return empty
                    # If we have some blocks, continue with what we have
                    has_more = False
                    continue
                elif "Could not find block" in error_message:
                    logger.warning(
                        f"Block not found in page {page_id}, continuing with available blocks: {error_message}"
                    )
                    has_more = False
                    continue
                # Re-raise other API errors (after retry exhaustion)
                raise

        if skipped_blocks_count > 0:
            logger.info(
                f"Page {page_id}: Skipped {skipped_blocks_count} unsupported block sections, "
                f"successfully processed {len(blocks)} blocks"
            )

        # Process nested blocks recursively
        processed_blocks = []
        for block in blocks:
            processed_block, block_had_skips = await self.process_block(block)
            if processed_block:  # Only add if block was processed successfully
                processed_blocks.append(processed_block)
            if block_had_skips:
                had_skipped_content = True

        return processed_blocks, had_skipped_content

    async def process_block(self, block) -> tuple[dict | None, bool]:
        """
        Processes a block and recursively fetches any child blocks.

        Args:
            block (dict): The block to process

        Returns:
            tuple: (Processed block dict or None, bool indicating if content was skipped)
        """
        notion = await self._get_client()

        block_id = block["id"]
        block_type = block["type"]
        had_skipped_content = False

        # Check if this is a known unsupported block type before processing
        if block_type in UNSUPPORTED_BLOCK_TYPES:
            logger.debug(
                f"Skipping unsupported block type: {block_type} (block_id: {block_id})"
            )
            return (
                {
                    "id": block_id,
                    "type": block_type,
                    "content": f"[{block_type} block - not supported by Notion API]",
                    "children": [],
                },
                True,  # Content was skipped
            )

        # Extract block content based on its type
        content = self.extract_block_content(block)

        # Check if block has children
        has_children = block.get("has_children", False)
        child_blocks = []

        if has_children:
            try:
                # Use retry wrapper for blocks.children.list API call
                children_response = await self._api_call_with_retry(
                    notion.blocks.children.list,
                    on_retry=self._on_retry_callback,
                    block_id=block_id,
                )
                for child_block in children_response["results"]:
                    processed_child, child_had_skips = await self.process_block(
                        child_block
                    )
                    if processed_child:
                        child_blocks.append(processed_child)
                    if child_had_skips:
                        had_skipped_content = True
            except APIResponseError as e:
                error_message = str(e)
                # Check if this is an unsupported block type error
                if any(err in error_message for err in UNSUPPORTED_BLOCK_TYPE_ERRORS):
                    logger.warning(
                        f"Skipping children of block {block_id} due to unsupported block type: {error_message}"
                    )
                    had_skipped_content = True
                    # Continue without children instead of failing
                elif "Could not find block" in error_message:
                    logger.warning(
                        f"Block {block_id} children not accessible, skipping: {error_message}"
                    )
                    # Continue without children
                else:
                    # Re-raise other API errors (after retry exhaustion)
                    raise

        return (
            {
                "id": block_id,
                "type": block_type,
                "content": content,
                "children": child_blocks,
            },
            had_skipped_content,
        )

    def extract_block_content(self, block):
        """
        Extracts the content from a block based on its type.

        Args:
            block (dict): The block to extract content from

        Returns:
            str: Extracted content as a string
        """
        block_type = block["type"]

        # Different block types have different structures
        if block_type in block and "rich_text" in block[block_type]:
            return "".join(
                [text_obj["plain_text"] for text_obj in block[block_type]["rich_text"]]
            )
        elif block_type == "image":
            # Instead of returning the raw URL which may contain sensitive AWS credentials,
            # return a placeholder or reference to the image
            if "file" in block["image"]:
                # For Notion-hosted images (which use AWS S3 pre-signed URLs)
                return "[Notion Image]"
            elif "external" in block["image"]:
                # For external images, we can return a sanitized reference
                url = block["image"]["external"]["url"]
                # Only return the domain part of external URLs to avoid potential sensitive parameters
                try:
                    from urllib.parse import urlparse

                    parsed_url = urlparse(url)
                    return f"[External Image from {parsed_url.netloc}]"
                except Exception:
                    return "[External Image]"
        elif block_type == "code":
            language = block["code"]["language"]
            code_text = "".join(
                [text_obj["plain_text"] for text_obj in block["code"]["rich_text"]]
            )
            return f"```{language}\n{code_text}\n```"
        elif block_type == "equation":
            return block["equation"]["expression"]
        # Add more block types as needed

        # Return empty string for unsupported block types
        return ""
