"""
Tests for RBAC schemas.

This module tests the Pydantic schemas used for role-based access control.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.rbac_schemas import (
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteBase,
    InviteCreate,
    InviteInfoResponse,
    InviteRead,
    InviteUpdate,
    MembershipBase,
    MembershipRead,
    MembershipReadWithUser,
    MembershipUpdate,
    PermissionInfo,
    PermissionsListResponse,
    RoleBase,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserSearchSpaceAccess,
)


class TestRoleSchemas:
    """Tests for role-related schemas."""

    def test_role_base_minimal(self):
        """Test RoleBase with minimal data."""
        role = RoleBase(name="TestRole")
        assert role.name == "TestRole"
        assert role.description is None
        assert role.permissions == []
        assert role.is_default is False

    def test_role_base_full(self):
        """Test RoleBase with all fields."""
        role = RoleBase(
            name="Admin",
            description="Administrator role",
            permissions=["documents:read", "documents:write"],
            is_default=True,
        )
        assert role.name == "Admin"
        assert role.description == "Administrator role"
        assert len(role.permissions) == 2
        assert role.is_default is True

    def test_role_base_name_validation(self):
        """Test RoleBase name length validation."""
        # Empty name should fail
        with pytest.raises(ValidationError):
            RoleBase(name="")
        
        # Name at max length should work
        role = RoleBase(name="x" * 100)
        assert len(role.name) == 100
        
        # Name over max length should fail
        with pytest.raises(ValidationError):
            RoleBase(name="x" * 101)

    def test_role_base_description_validation(self):
        """Test RoleBase description length validation."""
        # Description at max length should work
        role = RoleBase(name="Test", description="x" * 500)
        assert len(role.description) == 500
        
        # Description over max length should fail
        with pytest.raises(ValidationError):
            RoleBase(name="Test", description="x" * 501)

    def test_role_create(self):
        """Test RoleCreate schema."""
        role = RoleCreate(
            name="Editor",
            permissions=["documents:create", "documents:read"],
        )
        assert role.name == "Editor"

    def test_role_update_partial(self):
        """Test RoleUpdate with partial data."""
        update = RoleUpdate(name="NewName")
        assert update.name == "NewName"
        assert update.description is None
        assert update.permissions is None
        assert update.is_default is None

    def test_role_update_full(self):
        """Test RoleUpdate with all fields."""
        update = RoleUpdate(
            name="UpdatedRole",
            description="Updated description",
            permissions=["chats:read"],
            is_default=True,
        )
        assert update.permissions == ["chats:read"]

    def test_role_read(self):
        """Test RoleRead schema."""
        now = datetime.now(timezone.utc)
        role = RoleRead(
            id=1,
            name="Viewer",
            description="View-only access",
            permissions=["documents:read"],
            is_default=False,
            search_space_id=5,
            is_system_role=True,
            created_at=now,
        )
        assert role.id == 1
        assert role.is_system_role is True
        assert role.search_space_id == 5


class TestMembershipSchemas:
    """Tests for membership-related schemas."""

    def test_membership_base(self):
        """Test MembershipBase schema."""
        membership = MembershipBase()
        assert membership is not None

    def test_membership_update(self):
        """Test MembershipUpdate schema."""
        update = MembershipUpdate(role_id=5)
        assert update.role_id == 5

    def test_membership_update_optional(self):
        """Test MembershipUpdate with no data."""
        update = MembershipUpdate()
        assert update.role_id is None

    def test_membership_read(self):
        """Test MembershipRead schema."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        membership = MembershipRead(
            id=1,
            user_id=user_id,
            search_space_id=10,
            role_id=2,
            is_owner=False,
            joined_at=now,
            created_at=now,
            role=None,
        )
        assert membership.user_id == user_id
        assert membership.search_space_id == 10
        assert membership.is_owner is False

    def test_membership_read_with_role(self):
        """Test MembershipRead with nested role."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        role = RoleRead(
            id=2,
            name="Editor",
            permissions=["documents:create"],
            is_default=True,
            search_space_id=10,
            is_system_role=True,
            created_at=now,
        )
        membership = MembershipRead(
            id=1,
            user_id=user_id,
            search_space_id=10,
            role_id=2,
            is_owner=False,
            joined_at=now,
            created_at=now,
            role=role,
        )
        assert membership.role.name == "Editor"

    def test_membership_read_with_user(self):
        """Test MembershipReadWithUser schema."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        membership = MembershipReadWithUser(
            id=1,
            user_id=user_id,
            search_space_id=10,
            role_id=2,
            is_owner=True,
            joined_at=now,
            created_at=now,
            user_email="test@example.com",
            user_is_active=True,
        )
        assert membership.user_email == "test@example.com"
        assert membership.user_is_active is True


class TestInviteSchemas:
    """Tests for invite-related schemas."""

    def test_invite_base_minimal(self):
        """Test InviteBase with minimal data."""
        invite = InviteBase()
        assert invite.name is None
        assert invite.role_id is None
        assert invite.expires_at is None
        assert invite.max_uses is None

    def test_invite_base_full(self):
        """Test InviteBase with all fields."""
        expires = datetime.now(timezone.utc)
        invite = InviteBase(
            name="Team Invite",
            role_id=3,
            expires_at=expires,
            max_uses=10,
        )
        assert invite.name == "Team Invite"
        assert invite.max_uses == 10

    def test_invite_base_max_uses_validation(self):
        """Test InviteBase max_uses must be >= 1."""
        with pytest.raises(ValidationError):
            InviteBase(max_uses=0)
        
        # Valid minimum
        invite = InviteBase(max_uses=1)
        assert invite.max_uses == 1

    def test_invite_create(self):
        """Test InviteCreate schema."""
        invite = InviteCreate(
            name="Dev Team",
            role_id=2,
            max_uses=5,
        )
        assert invite.name == "Dev Team"

    def test_invite_update_partial(self):
        """Test InviteUpdate with partial data."""
        update = InviteUpdate(is_active=False)
        assert update.is_active is False
        assert update.name is None

    def test_invite_update_full(self):
        """Test InviteUpdate with all fields."""
        expires = datetime.now(timezone.utc)
        update = InviteUpdate(
            name="Updated Invite",
            role_id=4,
            expires_at=expires,
            max_uses=20,
            is_active=True,
        )
        assert update.name == "Updated Invite"

    def test_invite_read(self):
        """Test InviteRead schema."""
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        invite = InviteRead(
            id=1,
            invite_code="abc123xyz",
            search_space_id=5,
            created_by_id=user_id,
            uses_count=3,
            is_active=True,
            created_at=now,
        )
        assert invite.invite_code == "abc123xyz"
        assert invite.uses_count == 3

    def test_invite_accept_request(self):
        """Test InviteAcceptRequest schema."""
        request = InviteAcceptRequest(invite_code="valid-code-123")
        assert request.invite_code == "valid-code-123"

    def test_invite_accept_request_validation(self):
        """Test InviteAcceptRequest requires non-empty code."""
        with pytest.raises(ValidationError):
            InviteAcceptRequest(invite_code="")

    def test_invite_accept_response(self):
        """Test InviteAcceptResponse schema."""
        response = InviteAcceptResponse(
            message="Successfully joined",
            search_space_id=10,
            search_space_name="My Workspace",
            role_name="Editor",
        )
        assert response.message == "Successfully joined"
        assert response.search_space_name == "My Workspace"

    def test_invite_info_response(self):
        """Test InviteInfoResponse schema."""
        response = InviteInfoResponse(
            search_space_name="Public Space",
            role_name="Viewer",
            is_valid=True,
            message=None,
        )
        assert response.is_valid is True

    def test_invite_info_response_invalid(self):
        """Test InviteInfoResponse for invalid invite."""
        response = InviteInfoResponse(
            search_space_name="",
            role_name=None,
            is_valid=False,
            message="Invite has expired",
        )
        assert response.is_valid is False
        assert response.message == "Invite has expired"


class TestPermissionSchemas:
    """Tests for permission-related schemas."""

    def test_permission_info(self):
        """Test PermissionInfo schema."""
        perm = PermissionInfo(
            value="documents:create",
            name="Create Documents",
            category="Documents",
        )
        assert perm.value == "documents:create"
        assert perm.category == "Documents"

    def test_permissions_list_response(self):
        """Test PermissionsListResponse schema."""
        perms = [
            PermissionInfo(value="documents:read", name="Read Documents", category="Documents"),
            PermissionInfo(value="chats:read", name="Read Chats", category="Chats"),
        ]
        response = PermissionsListResponse(permissions=perms)
        assert len(response.permissions) == 2

    def test_permissions_list_response_empty(self):
        """Test PermissionsListResponse with empty list."""
        response = PermissionsListResponse(permissions=[])
        assert response.permissions == []


class TestUserAccessSchemas:
    """Tests for user access schemas."""

    def test_user_search_space_access(self):
        """Test UserSearchSpaceAccess schema."""
        access = UserSearchSpaceAccess(
            search_space_id=5,
            search_space_name="My Workspace",
            is_owner=True,
            role_name="Owner",
            permissions=["*"],
        )
        assert access.search_space_id == 5
        assert access.is_owner is True
        assert "*" in access.permissions

    def test_user_search_space_access_member(self):
        """Test UserSearchSpaceAccess for regular member."""
        access = UserSearchSpaceAccess(
            search_space_id=10,
            search_space_name="Team Space",
            is_owner=False,
            role_name="Editor",
            permissions=["documents:create", "documents:read", "chats:create"],
        )
        assert access.is_owner is False
        assert access.role_name == "Editor"
        assert len(access.permissions) == 3

    def test_user_search_space_access_no_role(self):
        """Test UserSearchSpaceAccess with no role."""
        access = UserSearchSpaceAccess(
            search_space_id=15,
            search_space_name="Guest Space",
            is_owner=False,
            role_name=None,
            permissions=[],
        )
        assert access.role_name is None
        assert access.permissions == []
