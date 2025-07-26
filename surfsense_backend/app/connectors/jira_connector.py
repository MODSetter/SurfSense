"""
Jira Connector Module

A module for retrieving data from Jira.
Allows fetching issue lists and their comments, projects and more.
"""

import base64
from datetime import datetime
from typing import Any

import requests


class JiraConnector:
    """Class for retrieving data from Jira."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        """
        Initialize the JiraConnector class.

        Args:
            base_url: Jira instance base URL (e.g., 'https://yourcompany.atlassian.net') (optional)
            email: Jira account email address (optional)
            api_token: Jira API token (optional)
        """
        self.base_url = base_url.rstrip("/") if base_url else None
        self.email = email
        self.api_token = api_token
        self.api_version = "3"  # Jira Cloud API version

    def set_credentials(self, base_url: str, email: str, api_token: str) -> None:
        """
        Set the Jira credentials.

        Args:
            base_url: Jira instance base URL
            email: Jira account email address
            api_token: Jira API token
        """
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token

    def set_email(self, email: str) -> None:
        """
        Set the Jira account email.

        Args:
            email: Jira account email address
        """
        self.email = email

    def set_api_token(self, api_token: str) -> None:
        """
        Set the Jira API token.

        Args:
            api_token: Jira API token
        """
        self.api_token = api_token

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for Jira API requests using Basic Authentication.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If email, api_token, or base_url have not been set
        """
        if not all([self.base_url, self.email, self.api_token]):
            raise ValueError(
                "Jira credentials not initialized. Call set_credentials() first."
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
        Make a request to the Jira API.

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
                "Jira credentials not initialized. Call set_credentials() first."
            )

        url = f"{self.base_url}/rest/api/{self.api_version}/{endpoint}"
        headers = self.get_headers()

        response = requests.get(url, headers=headers, params=params, timeout=500)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

    def get_all_projects(self) -> dict[str, Any]:
        """
        Fetch all projects from Jira.

        Returns:
            List of project objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        return self.make_api_request("project/search")

    def get_all_issues(self, project_key: str | None = None) -> list[dict[str, Any]]:
        """
        Fetch all issues from Jira.

        Args:
            project_key: Optional project key to filter issues (e.g., 'PROJ')

        Returns:
            List of issue objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        jql = "ORDER BY created DESC"
        if project_key:
            jql = f'project = "{project_key}" ' + jql

        fields = [
            "summary",
            "description",
            "status",
            "assignee",
            "reporter",
            "created",
            "updated",
            "priority",
            "issuetype",
            "project",
        ]

        params = {
            "jql": jql,
            "fields": ",".join(fields),
            "maxResults": 100,
            "startAt": 0,
        }

        all_issues = []
        start_at = 0

        while True:
            params["startAt"] = start_at
            result = self.make_api_request("search", params)

            if not isinstance(result, dict) or "issues" not in result:
                raise Exception("Invalid response from Jira API")

            issues = result["issues"]
            all_issues.extend(issues)

            print(f"Fetched {len(issues)} issues (startAt={start_at})")

            total = result.get("total", 0)
            if start_at + len(issues) >= total:
                break

            start_at += len(issues)

        return all_issues

    def get_issues_by_date_range(
        self,
        start_date: str,
        end_date: str,
        include_comments: bool = True,
        project_key: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch issues within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            include_comments: Whether to include comments in the response
            project_key: Optional project key to filter issues

        Returns:
            Tuple containing (issues list, error message or None)
        """
        try:
            # Build JQL query for date range
            # Query issues that were either created OR updated within the date range
            date_filter = (
                f"(createdDate >= '{start_date}' AND createdDate <= '{end_date}')"
            )
            # TODO : This JQL needs some improvement to work as expected

            _jql = f"{date_filter}"
            if project_key:
                _jql = (
                    f'project = "{project_key}" AND {date_filter} ORDER BY created DESC'
                )

            # Define fields to retrieve
            fields = [
                "summary",
                "description",
                "status",
                "assignee",
                "reporter",
                "created",
                "updated",
                "priority",
                "issuetype",
                "project",
            ]

            if include_comments:
                fields.append("comment")

            params = {
                # "jql": "",   TODO : Add a JQL query to filter from a date range
                "fields": ",".join(fields),
                "maxResults": 100,
                "startAt": 0,
            }

            all_issues = []
            start_at = 0

            while True:
                params["startAt"] = start_at

                result = self.make_api_request("search", params)

                if not isinstance(result, dict) or "issues" not in result:
                    return [], "Invalid response from Jira API"

                issues = result["issues"]
                all_issues.extend(issues)

                # Check if there are more issues to fetch
                total = result.get("total", 0)
                if start_at + len(issues) >= total:
                    break

                start_at += len(issues)

            if not all_issues:
                return [], "No issues found in the specified date range."

            return all_issues, None

        except Exception as e:
            return [], f"Error fetching issues: {e!s}"

    def format_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """
        Format an issue for easier consumption.

        Args:
            issue: The issue object from Jira API

        Returns:
            Formatted issue dictionary
        """
        fields = issue.get("fields", {})

        # Extract basic issue details
        formatted = {
            "id": issue.get("id", ""),
            "key": issue.get("key", ""),
            "title": fields.get("summary", ""),
            "description": fields.get("description", ""),
            "status": (
                fields.get("status", {}).get("name", "Unknown")
                if fields.get("status")
                else "Unknown"
            ),
            "status_category": (
                fields.get("status", {})
                .get("statusCategory", {})
                .get("name", "Unknown")
                if fields.get("status")
                else "Unknown"
            ),
            "priority": (
                fields.get("priority", {}).get("name", "Unknown")
                if fields.get("priority")
                else "Unknown"
            ),
            "issue_type": (
                fields.get("issuetype", {}).get("name", "Unknown")
                if fields.get("issuetype")
                else "Unknown"
            ),
            "project": (
                fields.get("project", {}).get("key", "Unknown")
                if fields.get("project")
                else "Unknown"
            ),
            "created_at": fields.get("created", ""),
            "updated_at": fields.get("updated", ""),
            "reporter": (
                {
                    "account_id": (
                        fields.get("reporter", {}).get("accountId", "")
                        if fields.get("reporter")
                        else ""
                    ),
                    "display_name": (
                        fields.get("reporter", {}).get("displayName", "Unknown")
                        if fields.get("reporter")
                        else "Unknown"
                    ),
                    "email": (
                        fields.get("reporter", {}).get("emailAddress", "")
                        if fields.get("reporter")
                        else ""
                    ),
                }
                if fields.get("reporter")
                else {"account_id": "", "display_name": "Unknown", "email": ""}
            ),
            "assignee": (
                {
                    "account_id": fields.get("assignee", {}).get("accountId", ""),
                    "display_name": fields.get("assignee", {}).get(
                        "displayName", "Unknown"
                    ),
                    "email": fields.get("assignee", {}).get("emailAddress", ""),
                }
                if fields.get("assignee")
                else None
            ),
            "comments": [],
        }

        # Extract comments if available
        if "comment" in fields and "comments" in fields["comment"]:
            for comment in fields["comment"]["comments"]:
                formatted_comment = {
                    "id": comment.get("id", ""),
                    "body": comment.get("body", ""),
                    "created_at": comment.get("created", ""),
                    "updated_at": comment.get("updated", ""),
                    "author": (
                        {
                            "account_id": (
                                comment.get("author", {}).get("accountId", "")
                                if comment.get("author")
                                else ""
                            ),
                            "display_name": (
                                comment.get("author", {}).get("displayName", "Unknown")
                                if comment.get("author")
                                else "Unknown"
                            ),
                            "email": (
                                comment.get("author", {}).get("emailAddress", "")
                                if comment.get("author")
                                else ""
                            ),
                        }
                        if comment.get("author")
                        else {"account_id": "", "display_name": "Unknown", "email": ""}
                    ),
                }
                formatted["comments"].append(formatted_comment)

        return formatted

    def format_issue_to_markdown(self, issue: dict[str, Any]) -> str:
        """
        Convert an issue to markdown format.

        Args:
            issue: The issue object (either raw or formatted)

        Returns:
            Markdown string representation of the issue
        """
        # Format the issue if it's not already formatted
        if "key" not in issue:
            issue = self.format_issue(issue)

        # Build the markdown content
        markdown = (
            f"# {issue.get('key', 'No Key')}: {issue.get('title', 'No Title')}\n\n"
        )

        if issue.get("status"):
            markdown += f"**Status:** {issue['status']}\n"

        if issue.get("priority"):
            markdown += f"**Priority:** {issue['priority']}\n"

        if issue.get("issue_type"):
            markdown += f"**Type:** {issue['issue_type']}\n"

        if issue.get("project"):
            markdown += f"**Project:** {issue['project']}\n\n"

        if issue.get("assignee") and issue["assignee"].get("display_name"):
            markdown += f"**Assignee:** {issue['assignee']['display_name']}\n"

        if issue.get("reporter") and issue["reporter"].get("display_name"):
            markdown += f"**Reporter:** {issue['reporter']['display_name']}\n"

        if issue.get("created_at"):
            created_date = self.format_date(issue["created_at"])
            markdown += f"**Created:** {created_date}\n"

        if issue.get("updated_at"):
            updated_date = self.format_date(issue["updated_at"])
            markdown += f"**Updated:** {updated_date}\n\n"

        if issue.get("description"):
            markdown += f"## Description\n\n{issue['description']}\n\n"

        if issue.get("comments"):
            markdown += f"## Comments ({len(issue['comments'])})\n\n"

            for comment in issue["comments"]:
                author_name = "Unknown"
                if comment.get("author") and comment["author"].get("display_name"):
                    author_name = comment["author"]["display_name"]

                comment_date = "Unknown date"
                if comment.get("created_at"):
                    comment_date = self.format_date(comment["created_at"])

                markdown += f"### {author_name} ({comment_date})\n\n{comment.get('body', '')}\n\n---\n\n"

        return markdown

    @staticmethod
    def format_date(iso_date: str) -> str:
        """
        Format an ISO date string to a more readable format.

        Args:
            iso_date: ISO format date string

        Returns:
            Formatted date string
        """
        if not iso_date or not isinstance(iso_date, str):
            return "Unknown date"

        try:
            # Jira dates are typically in format: 2023-01-01T12:00:00.000+0000
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return iso_date
