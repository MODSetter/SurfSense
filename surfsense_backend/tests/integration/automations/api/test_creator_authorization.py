from __future__ import annotations

import pytest

from app.app import app
from app.auth.context import AuthContext
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.db import User
from app.users import get_auth_context

pytestmark = pytest.mark.integration


async def test_only_creator_or_owner_can_change_an_automation(
    client,
    db_session,
    db_user: User,
    db_workspace,
    make_user,
    add_member,
) -> None:
    creator = await make_user()
    editor = await make_user()
    await add_member(db_workspace, creator, "Editor")
    await add_member(db_workspace, editor, "Editor")

    automation = Automation(
        workspace_id=db_workspace.id,
        created_by_user_id=creator.id,
        name="Creator's automation",
        definition={
            "name": "Creator's automation",
            "plan": [{"step_id": "s1", "action": "agent_task"}],
        },
    )
    db_session.add(automation)
    await db_session.flush()

    trigger = AutomationTrigger(
        automation_id=automation.id,
        type=TriggerType.SCHEDULE,
        params={"cron": "0 3 1 1 *", "timezone": "UTC"},
        static_inputs={},
        enabled=False,
    )
    db_session.add(trigger)
    await db_session.flush()

    def authenticate_as(user: User) -> None:
        async def override_auth() -> AuthContext:
            return AuthContext.session(user)

        app.dependency_overrides[get_auth_context] = override_auth

    authenticate_as(editor)
    denied = [
        await client.patch(
            f"/api/v1/automations/{automation.id}", json={"name": "Changed by editor"}
        ),
        await client.post(
            f"/api/v1/automations/{automation.id}/triggers",
            json={
                "type": "schedule",
                "params": {"cron": "0 3 1 1 *", "timezone": "UTC"},
                "enabled": False,
            },
        ),
        await client.patch(
            f"/api/v1/automations/{automation.id}/triggers/{trigger.id}",
            json={"enabled": True},
        ),
        await client.delete(
            f"/api/v1/automations/{automation.id}/triggers/{trigger.id}"
        ),
    ]
    assert [response.status_code for response in denied] == [403, 403, 403, 403]

    authenticate_as(creator)
    creator_update = await client.patch(
        f"/api/v1/automations/{automation.id}", json={"name": "Changed by creator"}
    )
    creator_trigger = await client.post(
        f"/api/v1/automations/{automation.id}/triggers",
        json={
            "type": "schedule",
            "params": {"cron": "0 3 1 1 *", "timezone": "UTC"},
            "enabled": False,
        },
    )
    assert creator_update.status_code == 200
    assert creator_trigger.status_code == 201

    authenticate_as(db_user)
    owner_update = await client.patch(
        f"/api/v1/automations/{automation.id}", json={"name": "Changed by owner"}
    )
    owner_trigger = await client.post(
        f"/api/v1/automations/{automation.id}/triggers",
        json={
            "type": "schedule",
            "params": {"cron": "0 3 1 1 *", "timezone": "UTC"},
            "enabled": False,
        },
    )
    assert owner_update.status_code == 200
    assert owner_trigger.status_code == 201
