"""
ClickUp Connector Module

A module for retrieving data from ClickUp.
Allows fetching tasks from workspaces and lists.
"""

from typing import Any

import requests


class ClickUpConnector:
    """Class for retrieving data from ClickUp."""

    def __init__(self, api_token: str | None = None):
        """
        Initialize the ClickUpConnector class.

        Args:
            api_token: ClickUp API token (optional)
        """
        self.api_token = api_token
        self.base_url = "https://api.clickup.com/api/v2"

    def set_api_token(self, api_token: str) -> None:
        """
        Set the ClickUp API token.

        Args:
            api_token: ClickUp API token
        """
        self.api_token = api_token

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for ClickUp API requests.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If api_token has not been set
        """
        if not self.api_token:
            raise ValueError(
                "ClickUp API token not initialized. Call set_api_token() first."
            )

        return {
            "Content-Type": "application/json",
            "Authorization": self.api_token,
        }

    def make_api_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a request to the ClickUp API.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters for the request (optional)

        Returns:
            Response data from the API

        Raises:
            ValueError: If api_token has not been set
            Exception: If the API request fails
        """
        if not self.api_token:
            raise ValueError(
                "ClickUp API token not initialized. Call set_api_token() first."
            )

        url = f"{self.base_url}/{endpoint}"
        headers = self.get_headers()

        response = requests.get(url, headers=headers, params=params, timeout=500)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

    def get_authorized_workspaces(self) -> dict[str, Any]:
        """
        Fetch authorized workspaces (teams) from ClickUp.

        Returns:
            Dictionary containing teams data

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        return self.make_api_request("team")

    def get_workspace_tasks(
        self, workspace_id: str, include_closed: bool = False
    ) -> list[dict[str, Any]]:
        """
        Fetch all tasks from a ClickUp workspace using the filtered team tasks endpoint.

        Args:
            workspace_id: ClickUp workspace (team) ID
            include_closed: Whether to include closed tasks (default: False)

        Returns:
            List of task objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        params = {
            "page": 0,
            "order_by": "created",
            "reverse": "true",
            "subtasks": "true",
            "include_closed": str(include_closed).lower(),
        }

        all_tasks = []
        page = 0

        while True:
            params["page"] = page
            result = self.make_api_request(f"team/{workspace_id}/task", params)

            if not isinstance(result, dict) or "tasks" not in result:
                break

            tasks = result["tasks"]
            if not tasks:
                break

            all_tasks.extend(tasks)

            # Check if there are more pages
            if len(tasks) < 100:  # ClickUp returns max 100 tasks per page
                break

            page += 1

        return all_tasks

    def get_tasks_in_date_range(
        self,
        workspace_id: str,
        start_date: str,
        end_date: str,
        include_closed: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch tasks from ClickUp within a specific date range.

        Args:
            workspace_id: ClickUp workspace (team) ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            include_closed: Whether to include closed tasks (default: False)

        Returns:
            Tuple containing (tasks list, error message or None)
        """
        try:
            # TODO : Include date range in api request

            params = {
                "page": 0,
                "order_by": "created",
                "reverse": "true",
                "subtasks": "true",
            }

            all_tasks = []
            page = 0

            while True:
                params["page"] = page
                result = self.make_api_request(f"team/{workspace_id}/task", params)

                if not isinstance(result, dict) or "tasks" not in result:
                    return [], "Invalid response from ClickUp API"

                tasks = result["tasks"]
                if not tasks:
                    break

                all_tasks.extend(tasks)

                # Check if there are more pages
                if len(tasks) < 100:  # ClickUp returns max 100 tasks per page
                    break

                page += 1

            if not all_tasks:
                return [], "No tasks found in the specified date range."

            return all_tasks, None

        except Exception as e:
            return [], f"Error fetching tasks: {e!s}"

    def get_task_details(self, task_id: str) -> dict[str, Any]:
        """
        Fetch detailed information about a specific task.

        Args:
            task_id: ClickUp task ID

        Returns:
            Task details

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        return self.make_api_request(f"task/{task_id}")

    def get_task_comments(self, task_id: str) -> dict[str, Any]:
        """
        Fetch comments for a specific task.

        Args:
            task_id: ClickUp task ID

        Returns:
            Task comments

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        return self.make_api_request(f"task/{task_id}/comment")
