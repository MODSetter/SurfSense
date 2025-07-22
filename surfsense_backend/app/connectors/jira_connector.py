"""
Jira Connector Module

A module for retrieving data from Jira.
Allows fetching issue lists and their comments, projects and more.
"""

from typing import Any, Dict, Optional

import requests


class JiraConnector:
    """Class for retrieving data from Jira."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        personal_access_token: Optional[str] = None,
    ):
        """
        Initialize the JiraConnector class.

        Args:
            base_url: Jira instance base URL (e.g., 'https://yourcompany.atlassian.net') (optional)
            personal_access_token: Jira personal access token (optional)
        """
        self.base_url = base_url
        self.personal_access_token = personal_access_token
        self.api_version = "3"  # Jira Cloud API version

    def set_personal_access_token(self, personal_access_token: str) -> None:
        """
        Set the Jira personal access token.

        Args:
            personal_access_token: Jira personal access token
        """
        self.personal_access_token = personal_access_token

    def get_headers(self) -> Dict[str, str]:
        """
        Get headers for Jira API requests.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If personal_access_token or base_url have not been set
        """
        if not all([self.base_url, self.personal_access_token]):
            raise ValueError("Jira personal access token or base URL not initialized.")

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.personal_access_token}",
            "Accept": "application/json",
        }

    def make_api_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Jira API.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters for the request (optional)

        Returns:
            Response data from the API

        Raises:
            ValueError: If personal_access_token or base_url have not been set
            Exception: If the API request fails
        """
        if not all([self.base_url, self.personal_access_token]):
            raise ValueError("Jira personal access token or base URL not initialized.")

        url = f"{self.base_url}/rest/api/{self.api_version}/{endpoint}"
        headers = self.get_headers()

        response = requests.get(url, headers=headers, params=params, timeout=500)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"API request failed with status code {response.status_code}: {response.text}"
            )
