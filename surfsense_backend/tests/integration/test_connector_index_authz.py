"""Cross-workspace authorization on the connector index endpoint.

``POST /search-source-connectors/{connector_id}/index?workspace_id=<X>`` must
authorize against the **connector's own** ``workspace_id`` (matching the
read/update/delete handlers), not the caller-supplied ``workspace_id`` query
parameter, and must reject a connector that does not belong to the requested
workspace.

Without this, a user who owns workspace B could index another user's
connector (which lives in space A) by passing ``workspace_id=B``: the
background indexer would run with the **victim connector's stored credentials**
and write the fetched content into the attacker's space. These tests pin that
boundary.
"""

from __future__ import annotations

import contextlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    Workspace,
)
from app.routes.search_source_connectors_routes import index_connector_content
from app.routes.workspaces_routes import create_default_roles_and_membership

pytestmark = pytest.mark.integration

# The handler imports ``check_permission`` into its own module namespace.
_CHECK_PERMISSION = "app.routes.search_source_connectors_routes.check_permission"


async def _make_user_with_space(session: AsyncSession) -> tuple[User, Workspace]:
    """A user plus a workspace they own, with the default roles/membership
    the ``POST /workspaces`` route would create (so ``check_permission`` would
    legitimately pass for this user on this space)."""
    user = User(
        id=uuid.uuid4(),
        email=f"authz-{uuid.uuid4()}@surfsense.test",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    space = Workspace(name=f"Space {uuid.uuid4().hex[:8]}", user_id=user.id)
    session.add(space)
    await session.flush()
    await create_default_roles_and_membership(session, space.id, user.id)
    await session.flush()
    return user, space


async def _make_connector(
    session: AsyncSession,
    owner: User,
    space: Workspace,
    connector_type: SearchSourceConnectorType,
) -> SearchSourceConnector:
    connector = SearchSourceConnector(
        name="Connector",
        connector_type=connector_type,
        # A stored credential the indexer would use — the thing a cross-tenant
        # index must never be able to abuse.
        config={
            "GITHUB_PAT": "victim-secret-pat",
            "repo_full_names": ["octocat/Hello-World"],
        },
        is_indexable=True,
        workspace_id=space.id,
        user_id=owner.id,
    )
    session.add(connector)
    await session.flush()
    return connector


class TestConnectorIndexCrossSpaceAuthz:
    async def test_cross_space_index_is_rejected_before_permission_check(
        self, db_session: AsyncSession
    ):
        """Attacker (owns space B) cannot index victim's connector (in space A)
        by passing ``workspace_id=B``.

        The mismatch is rejected with 404 **before** ``check_permission`` runs —
        which is essential, because that permission check *would* pass: the
        attacker legitimately holds ``CONNECTORS_UPDATE`` on their own space B.
        """
        victim, space_a = await _make_user_with_space(db_session)
        attacker, space_b = await _make_user_with_space(db_session)
        connector_a = await _make_connector(
            db_session, victim, space_a, SearchSourceConnectorType.GITHUB_CONNECTOR
        )

        with (
            patch(_CHECK_PERMISSION, new=AsyncMock()) as check_permission_mock,
            pytest.raises(HTTPException) as exc_info,
        ):
            await index_connector_content(
                connector_id=connector_a.id,
                workspace_id=space_b.id,  # the attacker's own space
                session=db_session,
                auth=AuthContext.session(attacker),
            )

        assert exc_info.value.status_code == 404
        # Rejected at the workspace reconciliation, never reaching (or relying
        # on) the permission check — which would have passed for space B.
        check_permission_mock.assert_not_awaited()

    async def test_same_space_index_authorizes_against_the_connectors_own_space(
        self, db_session: AsyncSession
    ):
        """A legitimate same-space index passes the reconciliation and authorizes
        ``check_permission`` against the connector's **own** workspace (not the
        client-supplied query param)."""
        owner, space = await _make_user_with_space(db_session)
        # A "live" connector type returns early (no Celery dispatch) right after
        # the permission check, so the call exercises the authz path cleanly.
        connector = await _make_connector(
            db_session, owner, space, SearchSourceConnectorType.CLICKUP_CONNECTOR
        )

        # Any downstream indexing behaviour is irrelevant to the authz contract
        # under test; we only assert what space was authorized.
        with (
            patch(_CHECK_PERMISSION, new=AsyncMock()) as check_permission_mock,
            contextlib.suppress(Exception),
        ):
            await index_connector_content(
                connector_id=connector.id,
                workspace_id=space.id,  # the connector's own space
                session=db_session,
                auth=AuthContext.session(owner),
            )

        check_permission_mock.assert_awaited_once()
        # The space passed to check_permission must be the connector's own space.
        assert connector.workspace_id in check_permission_mock.await_args.args
