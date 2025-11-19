"""
Jellyfin connector for media library access.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class JellyfinConnector:
    """Connector for Jellyfin media server API."""

    def __init__(self, server_url: str, api_key: str, user_id: str | None = None):
        """
        Initialize the Jellyfin connector.

        Args:
            server_url: Base URL of the Jellyfin server (e.g., http://localhost:8096)
            api_key: Jellyfin API key for authentication
            user_id: Optional user ID for user-specific data
        """
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.headers = {
            "X-Emby-Token": api_key,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> tuple[bool, str | None]:
        """
        Test the connection to Jellyfin server.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.server_url}/System/Info",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    info = response.json()
                    server_name = info.get("ServerName", "Unknown")
                    version = info.get("Version", "Unknown")
                    logger.info(
                        f"Connected to Jellyfin server: {server_name} v{version}"
                    )
                    return True, None
                elif response.status_code == 401:
                    return False, "Invalid API key"
                else:
                    return False, f"Server returned status {response.status_code}"

        except httpx.ConnectError as e:
            return False, f"Connection failed: {e!s}"
        except httpx.TimeoutException:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Unexpected error: {e!s}"

    async def get_users(self) -> tuple[list[dict], str | None]:
        """
        Get list of users on the server.

        Returns:
            Tuple of (users_list, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.server_url}/Users",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    return response.json(), None
                else:
                    return [], f"Failed to get users: {response.status_code}"

        except Exception as e:
            return [], f"Error getting users: {e!s}"

    async def get_libraries(self) -> tuple[list[dict], str | None]:
        """
        Get media libraries.

        Returns:
            Tuple of (libraries_list, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if self.user_id:
                    url = f"{self.server_url}/Users/{self.user_id}/Views"
                else:
                    url = f"{self.server_url}/Library/VirtualFolders"

                response = await client.get(url, headers=self.headers)

                if response.status_code == 200:
                    data = response.json()
                    # Handle different response formats
                    if isinstance(data, dict) and "Items" in data:
                        return data["Items"], None
                    elif isinstance(data, list):
                        return data, None
                    return [], None
                else:
                    return [], f"Failed to get libraries: {response.status_code}"

        except Exception as e:
            return [], f"Error getting libraries: {e!s}"

    async def get_items(
        self,
        parent_id: str | None = None,
        item_types: list[str] | None = None,
        limit: int = 100,
        start_index: int = 0,
        include_item_types: str | None = None,
    ) -> tuple[list[dict], int, str | None]:
        """
        Get media items from the library.

        Args:
            parent_id: Parent folder ID to filter by
            item_types: List of item types to include
            limit: Maximum items to return
            start_index: Starting index for pagination
            include_item_types: Comma-separated list of item types

        Returns:
            Tuple of (items_list, total_count, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    "Limit": limit,
                    "StartIndex": start_index,
                    "Recursive": "true",
                    "Fields": "Overview,Genres,Studios,People,ProviderIds,DateCreated,PremiereDate,ProductionYear,CommunityRating,OfficialRating,RunTimeTicks",
                    "SortBy": "DateCreated",
                    "SortOrder": "Descending",
                }

                if parent_id:
                    params["ParentId"] = parent_id

                if include_item_types:
                    params["IncludeItemTypes"] = include_item_types
                elif item_types:
                    params["IncludeItemTypes"] = ",".join(item_types)

                if self.user_id:
                    url = f"{self.server_url}/Users/{self.user_id}/Items"
                else:
                    url = f"{self.server_url}/Items"

                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("Items", [])
                    total = data.get("TotalRecordCount", len(items))
                    return items, total, None
                else:
                    return [], 0, f"Failed to get items: {response.status_code}"

        except Exception as e:
            return [], 0, f"Error getting items: {e!s}"

    async def get_favorites(self, limit: int = 100) -> tuple[list[dict], str | None]:
        """
        Get user's favorite items.

        Returns:
            Tuple of (favorites_list, error_message)
        """
        if not self.user_id:
            return [], "User ID required for favorites"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    "Limit": limit,
                    "Recursive": "true",
                    "Filters": "IsFavorite",
                    "Fields": "Overview,Genres,Studios,DateCreated,PremiereDate,ProductionYear,CommunityRating",
                    "SortBy": "DateCreated",
                    "SortOrder": "Descending",
                }

                response = await client.get(
                    f"{self.server_url}/Users/{self.user_id}/Items",
                    headers=self.headers,
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("Items", []), None
                else:
                    return [], f"Failed to get favorites: {response.status_code}"

        except Exception as e:
            return [], f"Error getting favorites: {e!s}"

    async def get_recently_played(
        self, limit: int = 100
    ) -> tuple[list[dict], str | None]:
        """
        Get user's recently played items.

        Returns:
            Tuple of (items_list, error_message)
        """
        if not self.user_id:
            return [], "User ID required for play history"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    "Limit": limit,
                    "Recursive": "true",
                    "Filters": "IsPlayed",
                    "Fields": "Overview,Genres,Studios,DateCreated,PremiereDate,ProductionYear,CommunityRating",
                    "SortBy": "DatePlayed",
                    "SortOrder": "Descending",
                }

                response = await client.get(
                    f"{self.server_url}/Users/{self.user_id}/Items",
                    headers=self.headers,
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("Items", []), None
                else:
                    return [], f"Failed to get play history: {response.status_code}"

        except Exception as e:
            return [], f"Error getting play history: {e!s}"

    async def get_all_indexable_data(
        self,
        max_items: int = 500,
        max_favorites: int = 100,
        max_recently_played: int = 100,
        item_types: list[str] | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Get all indexable data from Jellyfin.

        Args:
            max_items: Maximum library items to fetch
            max_favorites: Maximum favorites to fetch
            max_recently_played: Maximum recently played items to fetch
            item_types: Types of items to index (default: Movie, Series, Episode, Audio, MusicAlbum)

        Returns:
            Tuple of (items_list, error_message)
        """
        all_items = []
        errors = []

        # Default item types to index
        if item_types is None:
            item_types = ["Movie", "Series", "Episode", "Audio", "MusicAlbum", "Book", "AudioBook"]

        # Get library items
        include_types = ",".join(item_types)
        items, total, error = await self.get_items(
            limit=max_items, include_item_types=include_types
        )
        if error:
            errors.append(f"Library items: {error}")
        else:
            for item in items:
                all_items.append({"data": item, "source": "library"})
            logger.info(f"Fetched {len(items)} library items (total: {total})")

        # Get favorites if user_id is set
        if self.user_id:
            favorites, error = await self.get_favorites(limit=max_favorites)
            if error:
                errors.append(f"Favorites: {error}")
            else:
                # Avoid duplicates
                existing_ids = {item["data"].get("Id") for item in all_items}
                for item in favorites:
                    if item.get("Id") not in existing_ids:
                        all_items.append({"data": item, "source": "favorite"})
                logger.info(f"Fetched {len(favorites)} favorites")

            # Get recently played
            recently_played, error = await self.get_recently_played(
                limit=max_recently_played
            )
            if error:
                errors.append(f"Recently played: {error}")
            else:
                existing_ids = {item["data"].get("Id") for item in all_items}
                for item in recently_played:
                    if item.get("Id") not in existing_ids:
                        all_items.append({"data": item, "source": "recently_played"})
                logger.info(f"Fetched {len(recently_played)} recently played items")

        error_message = "; ".join(errors) if errors else None
        return all_items, error_message

    def format_item_to_markdown(self, item_data: dict) -> str:
        """
        Format a Jellyfin item to markdown for indexing.

        Args:
            item_data: Item data with 'data' and 'source' keys

        Returns:
            Formatted markdown string
        """
        item = item_data.get("data", {})
        source = item_data.get("source", "library")

        item_type = item.get("Type", "Unknown")
        name = item.get("Name", "Untitled")
        overview = item.get("Overview", "")
        year = item.get("ProductionYear", "")
        genres = item.get("Genres", [])
        rating = item.get("CommunityRating", "")
        official_rating = item.get("OfficialRating", "")
        studios = item.get("Studios", [])
        runtime_ticks = item.get("RunTimeTicks", 0)

        # Format runtime
        runtime = ""
        if runtime_ticks:
            minutes = runtime_ticks // 600000000
            hours = minutes // 60
            mins = minutes % 60
            if hours:
                runtime = f"{hours}h {mins}m"
            else:
                runtime = f"{mins}m"

        # Build markdown
        md_parts = [f"# {name}"]

        if year:
            md_parts.append(f"**Year:** {year}")

        md_parts.append(f"**Type:** {item_type}")

        if source == "favorite":
            md_parts.append("**Status:** Favorite")
        elif source == "recently_played":
            md_parts.append("**Status:** Recently Played")

        if official_rating:
            md_parts.append(f"**Rating:** {official_rating}")

        if rating:
            md_parts.append(f"**Community Score:** {rating}/10")

        if runtime:
            md_parts.append(f"**Runtime:** {runtime}")

        if genres:
            md_parts.append(f"**Genres:** {', '.join(genres)}")

        if studios:
            studio_names = [s.get("Name", "") for s in studios if s.get("Name")]
            if studio_names:
                md_parts.append(f"**Studios:** {', '.join(studio_names)}")

        # Add series info for episodes
        if item_type == "Episode":
            series_name = item.get("SeriesName", "")
            season_num = item.get("ParentIndexNumber", "")
            episode_num = item.get("IndexNumber", "")
            if series_name:
                md_parts.append(f"**Series:** {series_name}")
            if season_num and episode_num:
                md_parts.append(f"**Season/Episode:** S{season_num:02d}E{episode_num:02d}")

        # Add album/artist info for music
        if item_type in ["Audio", "MusicAlbum"]:
            album = item.get("Album", "")
            artists = item.get("Artists", [])
            if album:
                md_parts.append(f"**Album:** {album}")
            if artists:
                md_parts.append(f"**Artists:** {', '.join(artists)}")

        if overview:
            md_parts.append(f"\n## Overview\n{overview}")

        # Add people (cast/crew)
        people = item.get("People", [])
        if people:
            actors = [p.get("Name") for p in people if p.get("Type") == "Actor"][:5]
            directors = [p.get("Name") for p in people if p.get("Type") == "Director"]
            if actors:
                md_parts.append(f"\n**Cast:** {', '.join(actors)}")
            if directors:
                md_parts.append(f"**Director:** {', '.join(directors)}")

        return "\n".join(md_parts)
