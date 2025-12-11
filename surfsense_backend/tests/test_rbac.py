"""
Tests for the RBAC (Role-Based Access Control) utility functions.

These tests validate the security-critical RBAC behavior:
1. Users without membership should NEVER access resources
2. Permission checks must be strict - no false positives
3. Owners must have full access 
4. Role permissions must be properly enforced
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Skip these tests if app dependencies aren't installed
pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi_users")

from app.db import Permission, SearchSpaceMembership, SearchSpaceRole
from app.utils.rbac import (
    check_permission,
    check_search_space_access,
    generate_invite_code,
    get_default_role,
    get_owner_role,
    get_user_permissions,
    is_search_space_owner,
)


class TestSecurityCriticalAccessControl:
    """
    Critical security tests - these MUST pass to prevent unauthorized access.
    """

    @pytest.mark.asyncio
    async def test_non_member_cannot_access_search_space(self, mock_session, mock_user):
        """
        SECURITY: Non-members must be denied access with 403.
        This is critical - allowing access would be a security breach.
        """
        search_space_id = 1

        # Simulate user not being a member
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await check_search_space_access(mock_session, mock_user, search_space_id)

        # Must be 403 Forbidden, not 404 or other
        assert exc_info.value.status_code == 403
        assert "access" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_member_without_permission_is_denied(self, mock_session, mock_user):
        """
        SECURITY: Members without specific permission must be denied.
        Having membership alone is insufficient for sensitive operations.
        """
        search_space_id = 1

        # Member exists but has limited permissions (only read, not write)
        mock_role = MagicMock(spec=SearchSpaceRole)
        mock_role.permissions = ["documents:read"]  # Does NOT have write

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = False
        mock_membership.role = mock_role

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Attempt to access a write operation - must fail
        with patch("app.utils.rbac.has_permission", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(
                    mock_session,
                    mock_user,
                    search_space_id,
                    "documents:write",
                )

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_has_full_access_regardless_of_operation(
        self, mock_session, mock_user
    ):
        """
        SECURITY: Owners must have full access to all operations.
        This ensures owners can always manage their search spaces.
        """
        search_space_id = 1

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = True
        mock_membership.role = None  # Owners may not have explicit roles

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Owner should pass permission check with FULL_ACCESS
        with patch("app.utils.rbac.has_permission", return_value=True) as mock_has_perm:
            result = await check_permission(
                mock_session,
                mock_user,
                search_space_id,
                "any:permission",
            )

            assert result == mock_membership
            # Verify FULL_ACCESS was checked
            mock_has_perm.assert_called_once()
            call_args = mock_has_perm.call_args[0]
            assert Permission.FULL_ACCESS.value in call_args[0]


class TestGetUserPermissions:
    """Tests for permission retrieval - validates correct permission inheritance."""

    @pytest.mark.asyncio
    async def test_non_member_has_no_permissions(self, mock_session):
        """Non-members must have zero permissions."""
        user_id = uuid.uuid4()
        search_space_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_user_permissions(mock_session, user_id, search_space_id)

        assert result == []
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_owner_gets_full_access_permission(self, mock_session):
        """Owners must receive FULL_ACCESS permission."""
        user_id = uuid.uuid4()
        search_space_id = 1

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = True
        mock_membership.role = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_user_permissions(mock_session, user_id, search_space_id)

        assert Permission.FULL_ACCESS.value in result

    @pytest.mark.asyncio
    async def test_member_gets_only_role_permissions(self, mock_session):
        """Members should get exactly the permissions from their role - no more, no less."""
        user_id = uuid.uuid4()
        search_space_id = 1

        expected_permissions = ["documents:read", "chats:read"]

        mock_role = MagicMock(spec=SearchSpaceRole)
        mock_role.permissions = expected_permissions.copy()

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = False
        mock_membership.role = mock_role

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_user_permissions(mock_session, user_id, search_space_id)

        # Must match exactly - no extra permissions sneaking in
        assert set(result) == set(expected_permissions)
        assert len(result) == len(expected_permissions)

    @pytest.mark.asyncio
    async def test_member_without_role_has_no_permissions(self, mock_session):
        """Members without an assigned role must have empty permissions."""
        user_id = uuid.uuid4()
        search_space_id = 1

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = False
        mock_membership.role = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_user_permissions(mock_session, user_id, search_space_id)

        assert result == []


class TestOwnershipChecks:
    """Tests for ownership verification."""

    @pytest.mark.asyncio
    async def test_is_owner_returns_true_only_for_actual_owner(self, mock_session):
        """is_search_space_owner must return True ONLY for actual owners."""
        user_id = uuid.uuid4()
        search_space_id = 1

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_search_space_owner(mock_session, user_id, search_space_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_owner_returns_false_for_non_owner_member(self, mock_session):
        """Regular members must NOT be identified as owners."""
        user_id = uuid.uuid4()
        search_space_id = 1

        mock_membership = MagicMock(spec=SearchSpaceMembership)
        mock_membership.is_owner = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_search_space_owner(mock_session, user_id, search_space_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_owner_returns_false_for_non_member(self, mock_session):
        """Non-members must NOT be identified as owners."""
        user_id = uuid.uuid4()
        search_space_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_search_space_owner(mock_session, user_id, search_space_id)

        assert result is False


class TestInviteCodeSecurity:
    """Tests for invite code generation - validates security requirements."""

    def test_invite_codes_are_cryptographically_unique(self):
        """
        Invite codes must be cryptographically random to prevent guessing.
        Generate many codes and verify no collisions.
        """
        codes = set()
        num_codes = 1000

        for _ in range(num_codes):
            code = generate_invite_code()
            codes.add(code)

        # All codes must be unique - any collision indicates weak randomness
        assert len(codes) == num_codes

    def test_invite_code_has_sufficient_entropy(self):
        """
        Invite codes must have sufficient length for security.
        32 characters of URL-safe base64 = ~192 bits of entropy.
        """
        code = generate_invite_code()

        # Minimum 32 characters for adequate security
        assert len(code) >= 32

    def test_invite_code_is_url_safe(self):
        """Invite codes must be safe for use in URLs without encoding."""
        import re

        code = generate_invite_code()

        # Must only contain URL-safe characters
        assert re.match(r"^[A-Za-z0-9_-]+$", code) is not None

    def test_invite_codes_are_unpredictable(self):
        """
        Sequential invite codes must not be predictable.
        Verify no obvious patterns in consecutive codes.
        """
        codes = [generate_invite_code() for _ in range(10)]

        # No two consecutive codes should share significant prefixes
        for i in range(len(codes) - 1):
            # First 8 chars should differ between consecutive codes
            assert codes[i][:8] != codes[i + 1][:8]


class TestRoleRetrieval:
    """Tests for role lookup functions."""

    @pytest.mark.asyncio
    async def test_get_default_role_returns_correct_role(self, mock_session):
        """Default role lookup must return the role marked as default."""
        search_space_id = 1

        mock_role = MagicMock(spec=SearchSpaceRole)
        mock_role.name = "Viewer"
        mock_role.is_default = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_role
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_default_role(mock_session, search_space_id)

        assert result is not None
        assert result.is_default is True

    @pytest.mark.asyncio
    async def test_get_default_role_returns_none_when_no_default(self, mock_session):
        """Must return None if no default role exists - not raise an error."""
        search_space_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_default_role(mock_session, search_space_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_owner_role_returns_owner_named_role(self, mock_session):
        """Owner role lookup must return the role named 'Owner'."""
        search_space_id = 1

        mock_role = MagicMock(spec=SearchSpaceRole)
        mock_role.name = "Owner"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_role
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_owner_role(mock_session, search_space_id)

        assert result is not None
        assert result.name == "Owner"
