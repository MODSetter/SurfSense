"""
Mastodon/ActivityPub connector for fetching social media data.

This connector interfaces with the Mastodon REST API to retrieve:
- User's own posts (statuses)
- Favorited posts
- Bookmarked posts
- Notifications

Works with Mastodon, Pixelfed, and other Mastodon-compatible instances.
"""

import logging
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class MastodonConnector:
    """Connector for Mastodon and compatible ActivityPub platforms (Pixelfed, etc.)."""

    def __init__(self, instance_url: str, access_token: str):
        """
        Initialize the Mastodon connector.

        Args:
            instance_url: Base URL of Mastodon instance (e.g., https://mastodon.social)
            access_token: User access token for authentication
        """
        self.instance_url = instance_url.rstrip("/")
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self, endpoint: str, method: str = "GET", params: dict | None = None
    ) -> tuple[Any | None, str | None]:
        """
        Make an authenticated request to Mastodon API.

        Args:
            endpoint: API endpoint (e.g., /api/v1/accounts/verify_credentials)
            method: HTTP method
            params: Optional query parameters

        Returns:
            Tuple of (response_data, error_message)
        """
        url = f"{self.instance_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=self.headers, params=params, timeout=30
                ) as response:
                    if response.status == 200:
                        return await response.json(), None
                    elif response.status == 401:
                        return None, "Invalid or expired access token"
                    elif response.status == 403:
                        return None, "Access forbidden - check token scopes"
                    elif response.status == 404:
                        return None, f"Endpoint not found: {endpoint}"
                    elif response.status == 429:
                        return None, "Rate limit exceeded - try again later"
                    else:
                        error_text = await response.text()
                        return None, f"API error {response.status}: {error_text}"
        except aiohttp.ClientConnectorError as e:
            return None, f"Connection error: Unable to reach {self.instance_url}. {e!s}"
        except TimeoutError:
            return None, f"Request timeout connecting to {self.instance_url}"
        except Exception as e:
            return None, f"Unexpected error: {e!s}"

    async def _paginate_request(
        self, endpoint: str, params: dict | None = None, max_items: int = 200
    ) -> tuple[list[dict], str | None]:
        """
        Make paginated requests to fetch all items.

        Args:
            endpoint: API endpoint
            params: Optional query parameters
            max_items: Maximum number of items to fetch

        Returns:
            Tuple of (items_list, error_message)
        """
        all_items = []
        params = params or {}
        params["limit"] = min(40, max_items)  # Mastodon default max per page

        while len(all_items) < max_items:
            result, error = await self._make_request(endpoint, params=params)
            if error:
                if all_items:
                    # Return what we have so far
                    return all_items, f"Partial fetch: {error}"
                return [], error

            if not result:
                break

            all_items.extend(result)

            if len(result) < params["limit"]:
                # No more items
                break

            # Get the last item's ID for pagination
            if result:
                params["max_id"] = result[-1]["id"]

        return all_items[:max_items], None

    async def verify_credentials(self) -> tuple[dict | None, str | None]:
        """
        Verify the access token and get account info.

        Returns:
            Tuple of (account_info, error_message)
        """
        return await self._make_request("/api/v1/accounts/verify_credentials")

    async def test_connection(self) -> tuple[bool, str | None]:
        """
        Test the connection to the Mastodon instance.

        Returns:
            Tuple of (success, error_message)
        """
        result, error = await self.verify_credentials()
        if error:
            return False, error
        return True, None

    async def get_account_statuses(
        self, account_id: str, max_items: int = 100, since_id: str | None = None
    ) -> tuple[list[dict], str | None]:
        """
        Get statuses (posts) from a specific account.

        Args:
            account_id: The account ID
            max_items: Maximum number of statuses to fetch
            since_id: Only fetch statuses newer than this ID

        Returns:
            Tuple of (statuses_list, error_message)
        """
        params = {"exclude_replies": "false", "exclude_reblogs": "false"}
        if since_id:
            params["since_id"] = since_id

        return await self._paginate_request(
            f"/api/v1/accounts/{account_id}/statuses", params=params, max_items=max_items
        )

    async def get_own_statuses(
        self, max_items: int = 100, since_id: str | None = None
    ) -> tuple[list[dict], str | None]:
        """
        Get the authenticated user's own statuses.

        Args:
            max_items: Maximum number of statuses to fetch
            since_id: Only fetch statuses newer than this ID

        Returns:
            Tuple of (statuses_list, error_message)
        """
        # First get account info
        account, error = await self.verify_credentials()
        if error:
            return [], error

        return await self.get_account_statuses(
            account["id"], max_items=max_items, since_id=since_id
        )

    async def get_favourites(
        self, max_items: int = 100
    ) -> tuple[list[dict], str | None]:
        """
        Get the user's favorited statuses.

        Returns:
            Tuple of (favourites_list, error_message)
        """
        return await self._paginate_request(
            "/api/v1/favourites", max_items=max_items
        )

    async def get_bookmarks(
        self, max_items: int = 100
    ) -> tuple[list[dict], str | None]:
        """
        Get the user's bookmarked statuses.

        Returns:
            Tuple of (bookmarks_list, error_message)
        """
        return await self._paginate_request(
            "/api/v1/bookmarks", max_items=max_items
        )

    async def get_notifications(
        self, max_items: int = 50, types: list[str] | None = None
    ) -> tuple[list[dict], str | None]:
        """
        Get the user's notifications.

        Args:
            max_items: Maximum number of notifications to fetch
            types: Filter by notification types (mention, favourite, reblog, follow, poll, etc.)

        Returns:
            Tuple of (notifications_list, error_message)
        """
        params = {}
        if types:
            params["types[]"] = types

        return await self._paginate_request(
            "/api/v1/notifications", params=params, max_items=max_items
        )

    async def get_instance_info(self) -> tuple[dict | None, str | None]:
        """
        Get information about the Mastodon instance.

        Returns:
            Tuple of (instance_info, error_message)
        """
        # Try v2 first, fall back to v1
        result, error = await self._make_request("/api/v2/instance")
        if error:
            result, error = await self._make_request("/api/v1/instance")
        return result, error

    async def get_all_indexable_data(
        self,
        max_statuses: int = 100,
        max_favourites: int = 50,
        max_bookmarks: int = 50,
        since_id: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Get all data suitable for indexing.

        This includes:
        - User's own statuses
        - Favorited statuses
        - Bookmarked statuses

        Returns:
            Tuple of (indexable_items, error_message)
        """
        items = []
        errors = []

        # Get user's own statuses
        statuses, error = await self.get_own_statuses(
            max_items=max_statuses, since_id=since_id
        )
        if error:
            errors.append(f"Statuses: {error}")
        else:
            for status in statuses:
                items.append({
                    "type": "status",
                    "source": "own",
                    "data": status,
                })

        # Get favourites
        favourites, error = await self.get_favourites(max_items=max_favourites)
        if error:
            errors.append(f"Favourites: {error}")
        else:
            for status in favourites:
                items.append({
                    "type": "status",
                    "source": "favourite",
                    "data": status,
                })

        # Get bookmarks
        bookmarks, error = await self.get_bookmarks(max_items=max_bookmarks)
        if error:
            errors.append(f"Bookmarks: {error}")
        else:
            for status in bookmarks:
                items.append({
                    "type": "status",
                    "source": "bookmark",
                    "data": status,
                })

        error_msg = "; ".join(errors) if errors else None
        return items, error_msg

    def format_status_to_markdown(self, item: dict) -> str:
        """Format a status item to markdown."""
        source = item.get("source", "unknown")
        status = item.get("data", {})

        # Extract status info
        account = status.get("account", {})
        username = account.get("acct", "unknown")
        display_name = account.get("display_name", username)
        content = status.get("content", "")
        created_at = status.get("created_at", "")
        url = status.get("url", "")
        visibility = status.get("visibility", "public")

        # Clean HTML content (basic cleaning)
        import re
        content_text = re.sub(r"<[^>]+>", "", content)
        content_text = content_text.replace("&amp;", "&")
        content_text = content_text.replace("&lt;", "<")
        content_text = content_text.replace("&gt;", ">")
        content_text = content_text.replace("&quot;", '"')
        content_text = content_text.replace("&#39;", "'")

        # Build markdown
        source_label = {
            "own": "My Post",
            "favourite": "Favorited Post",
            "bookmark": "Bookmarked Post",
        }.get(source, "Post")

        md = f"# {source_label}\n\n"
        md += f"**Author:** {display_name} (@{username})\n"
        md += f"**Date:** {created_at}\n"
        md += f"**Visibility:** {visibility}\n"
        if url:
            md += f"**URL:** {url}\n"

        # Engagement stats
        reblogs = status.get("reblogs_count", 0)
        favourites = status.get("favourites_count", 0)
        replies = status.get("replies_count", 0)
        if reblogs or favourites or replies:
            md += f"**Engagement:** {reblogs} boosts, {favourites} favourites, {replies} replies\n"

        md += f"\n## Content\n\n{content_text}\n"

        # Media attachments
        media = status.get("media_attachments", [])
        if media:
            md += "\n## Media\n\n"
            for i, attachment in enumerate(media, 1):
                media_type = attachment.get("type", "unknown")
                media_url = attachment.get("url", "")
                description = attachment.get("description", "No description")
                md += f"{i}. [{media_type}]({media_url})"
                if description:
                    md += f" - {description}"
                md += "\n"

        # Tags/hashtags
        tags = status.get("tags", [])
        if tags:
            tag_names = [f"#{tag.get('name', '')}" for tag in tags]
            md += f"\n**Tags:** {' '.join(tag_names)}\n"

        # Mentions
        mentions = status.get("mentions", [])
        if mentions:
            mention_names = [f"@{m.get('acct', '')}" for m in mentions]
            md += f"**Mentions:** {' '.join(mention_names)}\n"

        # Poll if present
        poll = status.get("poll")
        if poll:
            md += "\n## Poll\n\n"
            for option in poll.get("options", []):
                title = option.get("title", "")
                votes = option.get("votes_count", 0)
                md += f"- {title}: {votes} votes\n"

        # Reblog info
        reblog = status.get("reblog")
        if reblog:
            reblog_account = reblog.get("account", {})
            md += f"\n*Boosted from @{reblog_account.get('acct', 'unknown')}*\n"

        return md

    def format_item_to_markdown(self, item: dict) -> str:
        """Format any item to markdown based on its type."""
        item_type = item.get("type", "")

        if item_type == "status":
            return self.format_status_to_markdown(item)
        else:
            # Generic formatting
            return f"# {item.get('type', 'Unknown')}\n\n{item}"
