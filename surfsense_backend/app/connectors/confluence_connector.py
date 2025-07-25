"""
Confluence Connector Module

A module for retrieving data from Confluence.
Allows fetching pages and their comments from specified spaces.
"""

import base64
from typing import Any, Dict, List, Optional

import requests


class ConfluenceConnector:
    """Class for retrieving data from Confluence."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
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

    def get_headers(self) -> Dict[str, str]:
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
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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

        response = requests.get(url, headers=headers, params=params, timeout=500)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

    def get_all_spaces(self) -> Dict[str, Any]:
        """
        Fetch all spaces from Confluence.

        Returns:
            Dictionary containing spaces data

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        all_spaces = []
        cursor = None

        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor

            result = self.make_api_request("spaces", params)

            if not isinstance(result, dict) or "results" not in result:
                raise Exception("Invalid response from Confluence API")

            spaces = result["results"]
            all_spaces.extend(spaces)

            # Check for next page using cursor-based pagination
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next URL if available
            next_url = links["next"]
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return {"results": all_spaces, "total": len(all_spaces)}

    def get_pages_in_space(self, space_id: str, include_body: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all pages in a specific space.

        Args:
            space_id: The ID of the space to fetch pages from
            include_body: Whether to include page body content (default: True)

        Returns:
            List of page objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        all_pages = []
        cursor = None

        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            if include_body:
                params["body-format"] = "storage"

            result = self.make_api_request(f"spaces/{space_id}/pages", params)

            if not isinstance(result, dict) or "results" not in result:
                raise Exception("Invalid response from Confluence API")

            pages = result["results"]
            all_pages.extend(pages)

            print(f"Fetched {len(pages)} pages from space {space_id} (cursor={cursor})")

            # Check for next page using cursor-based pagination
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next URL if available
            next_url = links["next"]
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_pages

    def get_page_comments(self, page_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch all comments (footer and inline) for a specific page.

        Args:
            page_id: The ID of the page to fetch comments from

        Returns:
            Dictionary with 'footer_comments' and 'inline_comments' keys

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        footer_comments = self._get_footer_comments_for_page(page_id)
        inline_comments = self._get_inline_comments_for_page(page_id)

        return {
            "footer_comments": footer_comments,
            "inline_comments": inline_comments
        }

    def _get_footer_comments_for_page(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch footer comments for a specific page.

        Args:
            page_id: The ID of the page to fetch footer comments from

        Returns:
            List of footer comment objects
        """
        all_comments = []
        cursor = None

        while True:
            params = {"limit": 100, "body-format": "storage"}
            if cursor:
                params["cursor"] = cursor

            result = self.make_api_request(f"pages/{page_id}/footer-comments", params)

            if not isinstance(result, dict) or "results" not in result:
                break  # No comments or error, return what we have

            comments = result["results"]
            all_comments.extend(comments)

            # Check for next page using cursor-based pagination
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next URL if available
            next_url = links["next"]
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_comments

    def _get_inline_comments_for_page(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch inline comments for a specific page.

        Args:
            page_id: The ID of the page to fetch inline comments from

        Returns:
            List of inline comment objects
        """
        all_comments = []
        cursor = None

        while True:
            params = {"limit": 100, "body-format": "storage"}
            if cursor:
                params["cursor"] = cursor

            result = self.make_api_request(f"pages/{page_id}/inline-comments", params)

            if not isinstance(result, dict) or "results" not in result:
                break  # No comments or error, return what we have

            comments = result["results"]
            all_comments.extend(comments)

            # Check for next page using cursor-based pagination
            links = result.get("_links", {})
            if "next" not in links:
                break

            # Extract cursor from next URL if available
            next_url = links["next"]
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[1].split("&")[0]
            else:
                break

        return all_comments

    def get_pages_and_comments_from_spaces(
        self,
        space_keys: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch all pages and their comments from specified spaces or all spaces.

        Args:
            space_keys: List of space keys to fetch from. If None, fetches from all spaces.
            start_date: Start date for filtering pages (YYYY-MM-DD format) - not implemented yet
            end_date: End date for filtering pages (YYYY-MM-DD format) - not implemented yet

        Returns:
            Tuple containing (pages with comments list, error message or None)
        """
        try:
            # Get all spaces first
            spaces_result = self.get_all_spaces()
            all_spaces = spaces_result.get("results", [])

            if not all_spaces:
                return [], "No spaces found in Confluence instance."

            # Filter spaces if space_keys provided
            if space_keys:
                filtered_spaces = [
                    space for space in all_spaces
                    if space.get("key") in space_keys
                ]
                if not filtered_spaces:
                    return [], f"No spaces found with keys: {space_keys}"
                spaces_to_process = filtered_spaces
            else:
                spaces_to_process = all_spaces

            all_pages_with_comments = []

            for space in spaces_to_process:
                space_id = space.get("id")
                space_key = space.get("key")
                space_name = space.get("name")

                print(f"Processing space: {space_name} ({space_key})")

                try:
                    # Get all pages in this space
                    pages = self.get_pages_in_space(space_id, include_body=True)

                    for page in pages:
                        page_id = page.get("id")
                        page_title = page.get("title")

                        print(f"Processing page: {page_title} (ID: {page_id})")

                        # Get comments for this page
                        try:
                            comments = self.get_page_comments(page_id)

                            # Add space and comment information to the page
                            page_with_comments = {
                                **page,
                                "space": {
                                    "id": space_id,
                                    "key": space_key,
                                    "name": space_name
                                },
                                "comments": comments
                            }

                            all_pages_with_comments.append(page_with_comments)

                        except Exception as e:
                            print(f"Warning: Failed to fetch comments for page {page_title}: {str(e)}")
                            # Add page without comments
                            page_with_comments = {
                                **page,
                                "space": {
                                    "id": space_id,
                                    "key": space_key,
                                    "name": space_name
                                },
                                "comments": {"footer_comments": [], "inline_comments": []}
                            }
                            all_pages_with_comments.append(page_with_comments)

                except Exception as e:
                    print(f"Warning: Failed to fetch pages from space {space_name}: {str(e)}")
                    continue

            if not all_pages_with_comments:
                return [], "No pages found in the specified spaces."

            return all_pages_with_comments, None

        except Exception as e:
            return [], f"Error fetching pages and comments: {str(e)}"