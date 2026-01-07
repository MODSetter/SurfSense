"""
Linear OAuth Utilities.

Provides functions for fetching user/organization info from Linear API.
Separated from linear_connector.py to avoid circular imports.
"""

import logging

import httpx

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

