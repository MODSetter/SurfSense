from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    Workspace,
)
from app.utils.oauth_security import OAuthStateManager

pytestmark = pytest.mark.integration


def _state_for(space_id: int, user_id: UUID, toolkit_id: str = "googledrive") -> str:
    return OAuthStateManager(config.SECRET_KEY).generate_secure_state(
        space_id=space_id,
        user_id=user_id,
        toolkit_id=toolkit_id,
    )


async def _drive_connectors(
    session: AsyncSession,
    *,
    user_id: UUID,
    workspace_id: int,
) -> list[SearchSourceConnector]:
    result = await session.execute(
        select(SearchSourceConnector).where(
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.workspace_id == workspace_id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        )
    )
    return list(result.scalars().all())


async def test_callback_with_error_param_redirects_to_denied_page(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    state = _state_for(db_workspace.id, db_user.id)

    response = await client.get(
        f"/api/v1/auth/composio/connector/callback?state={state}&error=access_denied"
    )

    assert response.status_code in {302, 303, 307}
    location = response.headers["location"]
    assert (
        f"/dashboard/{db_workspace.id}/connectors/callback?error=composio_oauth_denied"
    ) in location

    connectors = await _drive_connectors(
        db_session,
        user_id=db_user.id,
        workspace_id=db_workspace.id,
    )
    assert connectors == []


async def test_second_oauth_for_same_toolkit_takes_reconnection_branch(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    first_state = _state_for(db_workspace.id, db_user.id)

    first_response = await client.get(
        "/api/v1/auth/composio/connector/callback"
        f"?state={first_state}&connectedAccountId=fake-acct-googledrive-first"
    )

    assert first_response.status_code in {302, 303, 307}
    first_connectors = await _drive_connectors(
        db_session,
        user_id=db_user.id,
        workspace_id=db_workspace.id,
    )
    assert len(first_connectors) == 1
    first_connector = first_connectors[0]
    assert first_connector.config["composio_connected_account_id"] == (
        "fake-acct-googledrive-first"
    )

    second_state = _state_for(db_workspace.id, db_user.id)
    second_response = await client.get(
        "/api/v1/auth/composio/connector/callback"
        f"?state={second_state}&connectedAccountId=fake-acct-googledrive-second"
    )

    assert second_response.status_code in {302, 303, 307}
    second_connectors = await _drive_connectors(
        db_session,
        user_id=db_user.id,
        workspace_id=db_workspace.id,
    )
    assert len(second_connectors) == 1
    assert second_connectors[0].id == first_connector.id
    assert second_connectors[0].config["composio_connected_account_id"] == (
        "fake-acct-googledrive-second"
    )
