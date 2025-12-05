"""
BookStack Connector Module

A module for retrieving data from BookStack wiki systems.
Allows fetching pages, books, and chapters from BookStack instances.

BookStack API Documentation: https://demo.bookstackapp.com/api/docs
"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class BookStackConnector:
    """Class for retrieving data from BookStack."""

    # Rate limiting: 180 requests per minute = 0.33 seconds per request
    # Using 0.35 seconds to be safe
    REQUEST_INTERVAL = 0.35

    def __init__(
        self,
        base_url: str | None = None,
        token_id: str | None = None,
        token_secret: str | None = None,
    ):
        """
        Initialize the BookStackConnector class.

        Args:
            base_url: BookStack instance base URL (e.g., 'https://docs.example.com')
            token_id: BookStack API Token ID
            token_secret: BookStack API Token Secret
        """
        self.base_url = base_url.rstrip("/") if base_url else None
        self.token_id = token_id
        self.token_secret = token_secret
        self._last_request_time = 0.0

    def set_credentials(self, base_url: str, token_id: str, token_secret: str) -> None:
        """
        Set the BookStack credentials.

        Args:
            base_url: BookStack instance base URL
            token_id: BookStack API Token ID
            token_secret: BookStack API Token Secret

        Raises:
            ValueError: If any required credential is missing or invalid
        """
        if not base_url or not isinstance(base_url, str):
            raise ValueError("base_url must be a non-empty string")
        if not token_id or not isinstance(token_id, str):
            raise ValueError("token_id must be a non-empty string")
        if not token_secret or not isinstance(token_secret, str):
            raise ValueError("token_secret must be a non-empty string")

        self.base_url = base_url.rstrip("/")
        self.token_id = token_id
        self.token_secret = token_secret

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for BookStack API requests using Token Authentication.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If token_id, token_secret, or base_url have not been set
        """
        if not all([self.base_url, self.token_id, self.token_secret]):
            raise ValueError(
                "BookStack credentials not initialized. Call set_credentials() first."
            )

        return {
            "Authorization": f"Token {self.token_id}:{self.token_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _rate_limit(self) -> None:
        """Apply rate limiting between API requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    # Maximum retries for rate limit errors
    MAX_RATE_LIMIT_RETRIES = 3

    def make_api_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        raw_response: bool = False,
        _retry_count: int = 0,
    ) -> dict[str, Any] | str:
        """
        Make a request to the BookStack API.

        Args:
            endpoint: API endpoint (without base URL, e.g., 'pages' or 'pages/1')
            params: Query parameters for the request (optional)
            raw_response: If True, return raw text response instead of JSON

        Returns:
            Response data from the API (dict for JSON, str for raw)

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        if not all([self.base_url, self.token_id, self.token_secret]):
            raise ValueError(
                "BookStack credentials not initialized. Call set_credentials() first."
            )

        # Apply rate limiting
        self._rate_limit()

        url = f"{self.base_url}/api/{endpoint}"
        headers = self.get_headers()

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            if raw_response:
                return response.text
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                if _retry_count >= self.MAX_RATE_LIMIT_RETRIES:
                    raise Exception(
                        f"BookStack API rate limit exceeded after {self.MAX_RATE_LIMIT_RETRIES} retries"
                    ) from e
                logger.warning(
                    f"Rate limit exceeded, waiting 60 seconds... (retry {_retry_count + 1}/{self.MAX_RATE_LIMIT_RETRIES})"
                )
                time.sleep(60)
                return self.make_api_request(
                    endpoint, params, raw_response, _retry_count + 1
                )
            raise Exception(f"BookStack API request failed: {e!s}") from e
        except requests.exceptions.RequestException as e:
            raise Exception(f"BookStack API request failed: {e!s}") from e

    def get_all_pages(self, count: int = 500) -> list[dict[str, Any]]:
        """
        Fetch all pages from BookStack with pagination.

        Args:
            count: Number of records per request (max 500)

        Returns:
            List of page objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        all_pages = []
        offset = 0

        while True:
            params = {
                "count": min(count, 500),
                "offset": offset,
            }

            result = self.make_api_request("pages", params)

            if not isinstance(result, dict) or "data" not in result:
                raise Exception("Invalid response from BookStack API")

            pages = result["data"]
            all_pages.extend(pages)

            logger.info(f"Fetched {len(pages)} pages (offset: {offset})")

            # Check if we've fetched all pages
            total = result.get("total", 0)
            if offset + len(pages) >= total:
                break

            offset += len(pages)

        logger.info(f"Total pages fetched: {len(all_pages)}")
        return all_pages

    def get_page_detail(self, page_id: int) -> dict[str, Any]:
        """
        Get detailed information for a single page.

        The response includes 'html' (rendered) and optionally 'markdown' content.

        Args:
            page_id: The ID of the page

        Returns:
            Page detail object with content

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        result = self.make_api_request(f"pages/{page_id}")

        if not isinstance(result, dict):
            raise Exception(f"Invalid response for page {page_id}")

        return result

    def export_page_markdown(self, page_id: int) -> str:
        """
        Export a page as Markdown content.

        Args:
            page_id: The ID of the page

        Returns:
            Markdown content as string

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        result = self.make_api_request(
            f"pages/{page_id}/export/markdown", raw_response=True
        )
        return result if isinstance(result, str) else ""

    def get_book_detail(self, book_id: int) -> dict[str, Any]:
        """
        Get detailed information for a single book.

        The response includes a 'content' property with the book's structure.

        Args:
            book_id: The ID of the book

        Returns:
            Book detail object

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        result = self.make_api_request(f"books/{book_id}")

        if not isinstance(result, dict):
            raise Exception(f"Invalid response for book {book_id}")

        return result

    def get_pages_by_date_range(
        self,
        start_date: str,
        end_date: str,
        count: int = 500,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch pages updated within a specific date range.

        Uses the filter[updated_at:gt] parameter for incremental indexing.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (currently unused, for future use)
            count: Number of records per request (max 500)

        Returns:
            Tuple of (list of page objects, error message or None)

        Raises:
            ValueError: If credentials have not been set
        """
        all_pages = []
        offset = 0

        try:
            while True:
                params = {
                    "count": min(count, 500),
                    "offset": offset,
                    "filter[updated_at:gt]": start_date,
                    "sort": "-updated_at",  # Most recently updated first
                }

                result = self.make_api_request("pages", params)

                if not isinstance(result, dict) or "data" not in result:
                    return [], "Invalid response from BookStack API"

                pages = result["data"]
                all_pages.extend(pages)

                logger.info(
                    f"Fetched {len(pages)} pages updated after {start_date} (offset: {offset})"
                )

                # Check if we've fetched all pages
                total = result.get("total", 0)
                if offset + len(pages) >= total:
                    break

                offset += len(pages)

            if not all_pages:
                return [], f"No pages found updated after {start_date}"

            logger.info(
                f"Total pages fetched for date range {start_date} to {end_date}: {len(all_pages)}"
            )
            return all_pages, None

        except Exception as e:
            logger.error(f"Error fetching pages by date range: {e!s}", exc_info=True)
            return [], str(e)

    def get_page_with_content(
        self, page_id: int, use_markdown: bool = True
    ) -> tuple[dict[str, Any], str]:
        """
        Get page details along with its full content.

        Args:
            page_id: The ID of the page
            use_markdown: If True, export as Markdown; otherwise use HTML

        Returns:
            Tuple of (page detail dict, content string)

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        # Get page details first
        page_detail = self.get_page_detail(page_id)

        # Get content
        if use_markdown:
            try:
                content = self.export_page_markdown(page_id)
            except Exception as e:
                logger.warning(
                    f"Failed to export markdown for page {page_id}, falling back to HTML: {e}"
                )
                content = page_detail.get("html", "")
        else:
            content = page_detail.get("html", "")

        return page_detail, content
