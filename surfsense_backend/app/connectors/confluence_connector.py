"""
Confluence Connector Module

A module for retrieving data from Confluence.
Allows fetching pages and their comments from specified spaces.
"""

import base64
from typing import Any

import requests


class ConfluenceConnector:
    """Class for retrieving data from Confluence."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        """
        Initialize the ConfluenceConnector class.

        Args:
            base_url: Confluence instance base URL (e.g., 'https://yourcompany.atlassian.net') (optional)
            email: Confluence account email address (optional)
            api_token: Confluence API token (optional)
        """
        self.base_url = base_url.rstrip("/") if base_url else None
        self.email = email
        self.api_token = api_token
        self.api_version = "v2"  # Confluence Cloud API version

    def set_credentials(self, base_url: str, email: str, api_token: str) -> None:
        """
        Set the Confluence credentials.

        Args:
            base_url: Confluence instance base URL
            email: Confluence account email address
            api_token: Confluence API token
        """
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token

    def set_email(self, email: str) -> None:
        """
        Set the Confluence account email.

        Args:
            email: Confluence account email address
        """
        self.email = email

    def set_api_token(self, api_token: str) -> None:
        """
        Set the Confluence API token.

        Args:
            api_token: Confluence API token
        """
        self.api_token = api_token

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for Confluence API requests using Basic Authentication.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If email, api_token, or base_url have not been set
        """
        if not all([self.base_url, self.email, self.api_token]):
            raise ValueError(
                "Confluence credentials not initialized. Call set_credentials() first."
            )

        # Create Basic Auth header using email:api_token
        auth_str = f"{self.email}:{self.api_token}"
        auth_bytes = auth_str.encode("utf-8")
        auth_header = "Basic " + base64.b64encode(auth_bytes).decode("ascii")

        return {
            "Content-Type": "application/json",
            "Authorization": auth_header,
            "Accept": "application/json",
        }

    def make_api_request(
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
            ValueError: If email, api_token, or base_url have not been set
            Exception: If the API request fails
        """
        if not all([self.base_url, self.email, self.api_token]):
            raise ValueError(
                "Confluence credentials not initialized. Call set_credentials() first."
            )

        url = f"{self.base_url}/wiki/api/{self.api_version}/{endpoint}"
        headers = self.get_headers()

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Confluence API request failed: {e!s}") from e

    def get_all_spaces(self) -> list[dict[str, Any]]:
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

            result = self.make_api_request("spaces", params)

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

    def get_pages_in_space(
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

            result = self.make_api_request(f"spaces/{space_id}/pages", params)

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

    def get_page_comments(self, page_id: str) -> list[dict[str, Any]]:
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
        footer_comments = self._get_comments_for_page(page_id, "footer-comments")
        all_comments.extend(footer_comments)

        # Get inline comments
        inline_comments = self._get_comments_for_page(page_id, "inline-comments")
        all_comments.extend(inline_comments)

        return all_comments

    def _get_comments_for_page(
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

            result = self.make_api_request(f"pages/{page_id}/{comment_type}", params)

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

    def get_pages_by_date_range(
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
            all_pages = []

            if space_ids:
                # Fetch pages from specific spaces
                for space_id in space_ids:
                    pages = self.get_pages_in_space(space_id, include_body=True)
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

                    result = self.make_api_request("pages", params)
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
