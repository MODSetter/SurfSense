"""Unit tests for the agent revert service."""

from __future__ import annotations

from typing import Any

from app.services.revert_service import can_revert


class _FakeAction:
    def __init__(self, *, user_id: Any, tool_name: str = "edit_file") -> None:
        self.user_id = user_id
        self.tool_name = tool_name


class TestCanRevert:
    def test_owner_can_revert_their_own_action(self) -> None:
        action = _FakeAction(user_id="user-123")
        assert can_revert(requester_user_id="user-123", action=action, is_admin=False)

    def test_other_user_cannot_revert(self) -> None:
        action = _FakeAction(user_id="user-123")
        assert not can_revert(
            requester_user_id="someone-else", action=action, is_admin=False
        )

    def test_admin_always_allowed(self) -> None:
        action = _FakeAction(user_id="user-123")
        assert can_revert(requester_user_id="anybody", action=action, is_admin=True)

    def test_admin_can_revert_anonymous_action(self) -> None:
        action = _FakeAction(user_id=None)
        assert can_revert(requester_user_id="admin", action=action, is_admin=True)

    def test_anonymous_action_blocks_non_admin(self) -> None:
        action = _FakeAction(user_id=None)
        assert not can_revert(requester_user_id="user-1", action=action, is_admin=False)

    def test_uuid_string_normalization(self) -> None:
        """``user_id`` may be a UUID object; comparison should still work."""
        import uuid

        u = uuid.uuid4()
        action = _FakeAction(user_id=u)
        # Same UUID, passed as string from the requesting side.
        assert can_revert(requester_user_id=str(u), action=action, is_admin=False)
