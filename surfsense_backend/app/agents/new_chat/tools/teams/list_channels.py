import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from ._auth import GRAPH_API, get_access_token, get_teams_connector

logger = logging.getLogger(__name__)


def create_list_teams_channels_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def list_teams_channels() -> dict[str, Any]:
        """List all Microsoft Teams and their channels the user has access to.

        Returns:
            Dictionary with status and a list of teams, each containing
            team_id, team_name, and a list of channels (id, name).
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Teams tool not properly configured."}

        try:
            connector = await get_teams_connector(db_session, search_space_id, user_id)
            if not connector:
                return {"status": "error", "message": "No Teams connector found."}

            token = await get_access_token(db_session, connector)
            headers = {"Authorization": f"Bearer {token}"}

            async with httpx.AsyncClient(timeout=20.0) as client:
                teams_resp = await client.get(f"{GRAPH_API}/me/joinedTeams", headers=headers)

            if teams_resp.status_code == 401:
                return {"status": "auth_error", "message": "Teams token expired. Please re-authenticate.", "connector_type": "teams"}
            if teams_resp.status_code != 200:
                return {"status": "error", "message": f"Graph API error: {teams_resp.status_code}"}

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
                    result_teams.append({
                        "team_id": team_id,
                        "team_name": team.get("displayName", ""),
                        "channels": channels,
                    })

            return {"status": "success", "teams": result_teams, "total_teams": len(result_teams)}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error listing Teams channels: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to list Teams channels."}

    return list_teams_channels
