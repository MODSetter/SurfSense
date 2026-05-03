import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker

from ._auth import GRAPH_API, get_access_token, get_teams_connector

logger = logging.getLogger(__name__)


def create_list_teams_channels_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    """
    Factory function to create the list_teams_channels tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker` so the closure is safe to share across
    HTTP requests by the compiled-agent cache. Capturing a per-request
    session here would surface stale/closed sessions on cache hits.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.

    Returns:
        Configured list_teams_channels tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def list_teams_channels() -> dict[str, Any]:
        """List all Microsoft Teams and their channels the user has access to.

        Returns:
            Dictionary with status and a list of teams, each containing
            team_id, team_name, and a list of channels (id, name).
        """
        if search_space_id is None or user_id is None:
            return {"status": "error", "message": "Teams tool not properly configured."}

        try:
            async with async_session_maker() as db_session:
                connector = await get_teams_connector(
                    db_session, search_space_id, user_id
                )
                if not connector:
                    return {"status": "error", "message": "No Teams connector found."}

                token = await get_access_token(db_session, connector)
                headers = {"Authorization": f"Bearer {token}"}

                async with httpx.AsyncClient(timeout=20.0) as client:
                    teams_resp = await client.get(
                        f"{GRAPH_API}/me/joinedTeams", headers=headers
                    )

                if teams_resp.status_code == 401:
                    return {
                        "status": "auth_error",
                        "message": "Teams token expired. Please re-authenticate.",
                        "connector_type": "teams",
                    }
                if teams_resp.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"Graph API error: {teams_resp.status_code}",
                    }

                teams_data = teams_resp.json().get("value", [])
                result_teams = []

                async with httpx.AsyncClient(timeout=20.0) as client:
                    for team in teams_data:
                        team_id = team["id"]
                        ch_resp = await client.get(
                            f"{GRAPH_API}/teams/{team_id}/channels",
                            headers=headers,
                        )
                        channels = []
                        if ch_resp.status_code == 200:
                            channels = [
                                {"id": ch["id"], "name": ch.get("displayName", "")}
                                for ch in ch_resp.json().get("value", [])
                            ]
                        result_teams.append(
                            {
                                "team_id": team_id,
                                "team_name": team.get("displayName", ""),
                                "channels": channels,
                            }
                        )

                return {
                    "status": "success",
                    "teams": result_teams,
                    "total_teams": len(result_teams),
                }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error listing Teams channels: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to list Teams channels."}

    return list_teams_channels
