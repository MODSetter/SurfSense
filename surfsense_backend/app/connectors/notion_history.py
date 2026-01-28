import logging

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
                        f"Failed to decrypt Notion credentials: {e!s}"
                    ) from e

            try:
                self._credentials = NotionAuthCredentialsBase.from_dict(config_data)
            except Exception as e:
                raise ValueError(f"Invalid Notion credentials: {e!s}") from e

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
        search_params = {}

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
            if cursor:
                search_params["start_cursor"] = cursor

            search_results = await notion.search(**search_params)

            pages.extend(search_results["results"])
            has_more = search_results.get("has_more", False)

            if has_more:
                cursor = search_results.get("next_cursor")

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
                if cursor:
                    response = await notion.blocks.children.list(
                        block_id=page_id, start_cursor=cursor
                    )
                else:
                    response = await notion.blocks.children.list(block_id=page_id)

                blocks.extend(response["results"])
                has_more = response["has_more"]

                if has_more:
                    cursor = response["next_cursor"]

            except APIResponseError as e:
                error_message = str(e)
                # Check if this is an unsupported block type error
                if any(
                    err in error_message for err in UNSUPPORTED_BLOCK_TYPE_ERRORS
                ):
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
                # Re-raise other API errors
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
                # Fetch and process child blocks
                children_response = await notion.blocks.children.list(
                    block_id=block_id
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
                if any(
                    err in error_message for err in UNSUPPORTED_BLOCK_TYPE_ERRORS
                ):
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
                    # Re-raise other API errors
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
