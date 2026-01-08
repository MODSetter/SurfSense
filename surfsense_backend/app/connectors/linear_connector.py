"""
Linear Connector Module

A module for retrieving issues and comments from Linear.
Allows fetching issue lists and their comments with date range filtering.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
import requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector
from app.schemas.linear_auth_credentials import LinearAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"

ORGANIZATION_QUERY = """
query {
    organization {
        name
    }
}
"""


async def fetch_linear_organization_name(access_token: str) -> str | None:
    """
    Fetch organization/workspace name from Linear GraphQL API.

    Args:
        access_token: The Linear OAuth access token

    Returns:
        Organization name or None if fetch fails
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LINEAR_GRAPHQL_URL,
                headers={
                    "Authorization": access_token,
                    "Content-Type": "application/json",
                },
                json={"query": ORGANIZATION_QUERY},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                org_name = data.get("data", {}).get("organization", {}).get("name")
                if org_name:
                    logger.debug(f"Fetched Linear organization name: {org_name}")
                    return org_name

            logger.warning(f"Failed to fetch Linear org info: {response.status_code}")
            return None

    except Exception as e:
        logger.warning(f"Error fetching Linear organization name: {e!s}")
        return None


class LinearConnector:
    """Class for retrieving issues and comments from Linear."""

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: LinearAuthCredentialsBase | None = None,
    ):
        """
        Initialize the LinearConnector class with auto-refresh capability.

        Args:
            session: Database session for updating connector
            connector_id: Connector ID for direct updates
            credentials: Linear OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self.api_url = "https://api.linear.app/graphql"

    async def _get_valid_token(self) -> str:
        """
        Get valid Linear access token, refreshing if needed.

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
                        f"Decrypted Linear credentials for connector {self._connector_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt Linear credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        f"Failed to decrypt Linear credentials: {e!s}"
                    ) from e

            try:
                self._credentials = LinearAuthCredentialsBase.from_dict(config_data)
            except Exception as e:
                raise ValueError(f"Invalid Linear credentials: {e!s}") from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    f"Linear token expired for connector {self._connector_id}, refreshing..."
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

                # Lazy import to avoid circular dependency
                from app.routes.linear_add_connector_route import refresh_linear_token

                # Refresh token
                connector = await refresh_linear_token(self._session, connector)

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

                self._credentials = LinearAuthCredentialsBase.from_dict(config_data)

                logger.info(
                    f"Successfully refreshed Linear token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Linear token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Linear OAuth credentials: {e!s}"
                ) from e

        return self._credentials.access_token

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for Linear API requests.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If no Linear access token has been set
        """
        # This is a synchronous method, but we need async token refresh
        # For now, we'll raise an error if called directly
        # All API calls should go through execute_graphql_query which handles async refresh
        if not self._credentials or not self._credentials.access_token:
            raise ValueError(
                "Linear access token not initialized. Use execute_graphql_query() method."
            )

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._credentials.access_token}",
        }

    async def execute_graphql_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a GraphQL query against the Linear API with automatic token refresh.

        Args:
            query: GraphQL query string
            variables: Variables for the GraphQL query (optional)

        Returns:
            Response data from the API

        Raises:
            ValueError: If no Linear access token has been set
            Exception: If the API request fails
        """
        # Get valid token (refreshes if needed)
        access_token = await self._get_valid_token()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        payload = {"query": query}

        if variables:
            payload["variables"] = variables

        response = requests.post(self.api_url, headers=headers, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(
                f"Query failed with status code {response.status_code}: {response.text}"
            )

    async def get_all_issues(
        self, include_comments: bool = True
    ) -> list[dict[str, Any]]:
        """
        Fetch all issues from Linear.

        Args:
            include_comments: Whether to include comments in the response

        Returns:
            List of issue objects

        Raises:
            ValueError: If no Linear access token has been set
            Exception: If the API request fails
        """
        comments_query = ""
        if include_comments:
            comments_query = """
            comments {
                nodes {
                    id
                    body
                    user {
                        id
                        name
                        email
                    }
                    createdAt
                    updatedAt
                }
            }
            """

        query = f"""
        query {{
            issues {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    state {{
                        id
                        name
                        type
                    }}
                    assignee {{
                        id
                        name
                        email
                    }}
                    creator {{
                        id
                        name
                        email
                    }}
                    createdAt
                    updatedAt
                    {comments_query}
                }}
            }}
        }}
        """

        result = await self.execute_graphql_query(query)

        # Extract issues from the response
        if (
            "data" in result
            and "issues" in result["data"]
            and "nodes" in result["data"]["issues"]
        ):
            return result["data"]["issues"]["nodes"]

        return []

    async def get_issues_by_date_range(
        self, start_date: str, end_date: str, include_comments: bool = True
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch issues within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            include_comments: Whether to include comments in the response

        Returns:
            Tuple containing (issues list, error message or None)
        """
        # Validate date strings
        if not start_date or start_date.lower() in ("undefined", "null", "none"):
            return (
                [],
                "Invalid start_date: must be a valid date string in YYYY-MM-DD format",
            )
        if not end_date or end_date.lower() in ("undefined", "null", "none"):
            return (
                [],
                "Invalid end_date: must be a valid date string in YYYY-MM-DD format",
            )

        # Convert date strings to ISO format
        try:
            # For Linear API: we need to use a more specific format for the filter
            # Instead of DateTime, use a string in the filter for DateTimeOrDuration
            comments_query = ""
            if include_comments:
                comments_query = """
                comments {
                    nodes {
                        id
                        body
                        user {
                            id
                            name
                            email
                        }
                        createdAt
                        updatedAt
                    }
                }
                """

            # Query issues that were either created OR updated within the date range
            # This ensures we catch both new issues and updated existing issues
            query = f"""
            query IssuesByDateRange($after: String) {{
                issues(
                    first: 100,
                    after: $after,
                    filter: {{
                        or: [
                            {{
                                createdAt: {{
                                    gte: "{start_date}T00:00:00Z"
                                    lte: "{end_date}T23:59:59Z"
                                }}
                            }},
                            {{
                                updatedAt: {{
                                    gte: "{start_date}T00:00:00Z"
                                    lte: "{end_date}T23:59:59Z"
                                }}
                            }}
                        ]
                    }}
                ) {{
                    nodes {{
                        id
                        identifier
                        title
                        description
                        state {{
                            id
                            name
                            type
                        }}
                        assignee {{
                            id
                            name
                            email
                        }}
                        creator {{
                            id
                            name
                            email
                        }}
                        createdAt
                        updatedAt
                        {comments_query}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
            """

            try:
                all_issues = []
                has_next_page = True
                cursor = None

                # Handle pagination to get all issues
                while has_next_page:
                    variables = {"after": cursor} if cursor else {}
                    result = await self.execute_graphql_query(query, variables)

                    # Check for errors
                    if "errors" in result:
                        error_message = "; ".join(
                            [
                                error.get("message", "Unknown error")
                                for error in result["errors"]
                            ]
                        )
                        return [], f"GraphQL errors: {error_message}"

                    # Extract issues from the response
                    if "data" in result and "issues" in result["data"]:
                        issues_page = result["data"]["issues"]

                        # Add issues from this page
                        if "nodes" in issues_page:
                            all_issues.extend(issues_page["nodes"])

                        # Check if there are more pages
                        if "pageInfo" in issues_page:
                            page_info = issues_page["pageInfo"]
                            has_next_page = page_info.get("hasNextPage", False)
                            cursor = (
                                page_info.get("endCursor") if has_next_page else None
                            )
                        else:
                            has_next_page = False
                    else:
                        has_next_page = False

                if not all_issues:
                    return [], "No issues found in the specified date range."

                return all_issues, None

            except Exception as e:
                return [], f"Error fetching issues: {e!s}"

        except ValueError as e:
            return [], f"Invalid date format: {e!s}. Please use YYYY-MM-DD."

    def format_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """
        Format an issue for easier consumption.

        Args:
            issue: The issue object from Linear API

        Returns:
            Formatted issue dictionary
        """
        # Extract basic issue details
        formatted = {
            "id": issue.get("id", ""),
            "identifier": issue.get("identifier", ""),
            "title": issue.get("title", ""),
            "description": issue.get("description", ""),
            "state": issue.get("state", {}).get("name", "Unknown")
            if issue.get("state")
            else "Unknown",
            "state_type": issue.get("state", {}).get("type", "Unknown")
            if issue.get("state")
            else "Unknown",
            "created_at": issue.get("createdAt", ""),
            "updated_at": issue.get("updatedAt", ""),
            "creator": {
                "id": issue.get("creator", {}).get("id", "")
                if issue.get("creator")
                else "",
                "name": issue.get("creator", {}).get("name", "Unknown")
                if issue.get("creator")
                else "Unknown",
                "email": issue.get("creator", {}).get("email", "")
                if issue.get("creator")
                else "",
            }
            if issue.get("creator")
            else {"id": "", "name": "Unknown", "email": ""},
            "assignee": {
                "id": issue.get("assignee", {}).get("id", ""),
                "name": issue.get("assignee", {}).get("name", "Unknown"),
                "email": issue.get("assignee", {}).get("email", ""),
            }
            if issue.get("assignee")
            else None,
            "comments": [],
        }

        # Extract comments if available
        if "comments" in issue and "nodes" in issue["comments"]:
            for comment in issue["comments"]["nodes"]:
                formatted_comment = {
                    "id": comment.get("id", ""),
                    "body": comment.get("body", ""),
                    "created_at": comment.get("createdAt", ""),
                    "updated_at": comment.get("updatedAt", ""),
                    "user": {
                        "id": comment.get("user", {}).get("id", "")
                        if comment.get("user")
                        else "",
                        "name": comment.get("user", {}).get("name", "Unknown")
                        if comment.get("user")
                        else "Unknown",
                        "email": comment.get("user", {}).get("email", "")
                        if comment.get("user")
                        else "",
                    }
                    if comment.get("user")
                    else {"id": "", "name": "Unknown", "email": ""},
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
        if "identifier" not in issue:
            issue = self.format_issue(issue)

        # Build the markdown content
        markdown = f"# {issue.get('identifier', 'No ID')}: {issue.get('title', 'No Title')}\n\n"

        if issue.get("state"):
            markdown += f"**Status:** {issue['state']}\n\n"

        if issue.get("assignee") and issue["assignee"].get("name"):
            markdown += f"**Assignee:** {issue['assignee']['name']}\n"

        if issue.get("creator") and issue["creator"].get("name"):
            markdown += f"**Created by:** {issue['creator']['name']}\n"

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
                user_name = "Unknown"
                if comment.get("user") and comment["user"].get("name"):
                    user_name = comment["user"]["name"]

                comment_date = "Unknown date"
                if comment.get("created_at"):
                    comment_date = self.format_date(comment["created_at"])

                markdown += f"### {user_name} ({comment_date})\n\n{comment.get('body', '')}\n\n---\n\n"

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
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return iso_date
