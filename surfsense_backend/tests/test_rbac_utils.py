"""
Tests for RBAC utility functions.

This module tests the RBAC helper functions used for access control.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db import Permission
from app.utils.rbac import (
    check_permission,
    check_search_space_access,
    generate_invite_code,
    get_user_membership,
    get_user_permissions,
    is_search_space_owner,
)


class TestGenerateInviteCode:
    """Tests for generate_invite_code function."""

    def test_generates_string(self):
        """Test that function generates a string."""
        code = generate_invite_code()
        assert isinstance(code, str)

    def test_generates_unique_codes(self):
        """Test that function generates unique codes."""
        codes = {generate_invite_code() for _ in range(100)}
        assert len(codes) == 100  # All unique

    def test_code_is_url_safe(self):
        """Test that generated code is URL-safe."""
        code = generate_invite_code()
        # URL-safe characters: alphanumeric, hyphen, underscore
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in valid_chars for c in code)

    def test_code_length(self):
        """Test that generated code has expected length."""
        code = generate_invite_code()
        # token_urlsafe(24) produces ~32 characters
        assert len(code) == 32


class TestGetUserMembership:
    """Tests for get_user_membership function."""

    @pytest.mark.asyncio
    async def test_returns_membership(self):
        """Test returns membership when found."""
        mock_membership = MagicMock()
        mock_membership.is_owner = True
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_membership
        
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        
        user_id = uuid4()
        result = await get_user_membership(mock_session, user_id, 1)
        
        assert result == mock_membership
        assert result.is_owner is True

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Test returns None when membership not found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        
        user_id = uuid4()
        result = await get_user_membership(mock_session, user_id, 999)
        
        assert result is None


class TestGetUserPermissions:
    """Tests for get_user_permissions function."""

    @pytest.mark.asyncio
    async def test_owner_has_full_access(self):
        """Test owner gets FULL_ACCESS permission."""
        mock_membership = MagicMock()
        mock_membership.is_owner = True
        mock_membership.role = None
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            permissions = await get_user_permissions(mock_session, user_id, 1)
            
            assert Permission.FULL_ACCESS.value in permissions

    @pytest.mark.asyncio
    async def test_member_gets_role_permissions(self):
        """Test member gets permissions from their role."""
        mock_role = MagicMock()
        mock_role.permissions = ["documents:read", "chats:create"]
        
        mock_membership = MagicMock()
        mock_membership.is_owner = False
        mock_membership.role = mock_role
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            permissions = await get_user_permissions(mock_session, user_id, 1)
            
            assert permissions == ["documents:read", "chats:create"]

    @pytest.mark.asyncio
    async def test_no_membership_returns_empty(self):
        """Test no membership returns empty permissions."""
        with patch("app.utils.rbac.get_user_membership", return_value=None):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            permissions = await get_user_permissions(mock_session, user_id, 1)
            
            assert permissions == []

    @pytest.mark.asyncio
    async def test_no_role_returns_empty(self):
        """Test member without role returns empty permissions."""
        mock_membership = MagicMock()
        mock_membership.is_owner = False
        mock_membership.role = None
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            permissions = await get_user_permissions(mock_session, user_id, 1)
            
            assert permissions == []


class TestCheckPermission:
    """Tests for check_permission function."""

    @pytest.mark.asyncio
    async def test_owner_passes_any_permission(self):
        """Test owner passes any permission check."""
        mock_membership = MagicMock()
        mock_membership.is_owner = True
        mock_membership.role = None
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            result = await check_permission(
                mock_session,
                mock_user,
                1,
                Permission.SETTINGS_DELETE.value,
            )
            
            assert result == mock_membership

    @pytest.mark.asyncio
    async def test_member_with_permission_passes(self):
        """Test member with required permission passes."""
        mock_role = MagicMock()
        mock_role.permissions = [Permission.DOCUMENTS_READ.value, Permission.CHATS_READ.value]
        
        mock_membership = MagicMock()
        mock_membership.is_owner = False
        mock_membership.role = mock_role
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            result = await check_permission(
                mock_session,
                mock_user,
                1,
                Permission.DOCUMENTS_READ.value,
            )
            
            assert result == mock_membership

    @pytest.mark.asyncio
    async def test_member_without_permission_raises(self):
        """Test member without required permission raises HTTPException."""
        mock_role = MagicMock()
        mock_role.permissions = [Permission.DOCUMENTS_READ.value]
        
        mock_membership = MagicMock()
        mock_membership.is_owner = False
        mock_membership.role = mock_role
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(
                    mock_session,
                    mock_user,
                    1,
                    Permission.DOCUMENTS_DELETE.value,
                )
            
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_no_membership_raises(self):
        """Test user without membership raises HTTPException."""
        with patch("app.utils.rbac.get_user_membership", return_value=None):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(
                    mock_session,
                    mock_user,
                    1,
                    Permission.DOCUMENTS_READ.value,
                )
            
            assert exc_info.value.status_code == 403
            assert "access to this search space" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_custom_error_message(self):
        """Test custom error message is used."""
        mock_role = MagicMock()
        mock_role.permissions = []
        
        mock_membership = MagicMock()
        mock_membership.is_owner = False
        mock_membership.role = mock_role
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(
                    mock_session,
                    mock_user,
                    1,
                    Permission.DOCUMENTS_DELETE.value,
                    error_message="Custom error message",
                )
            
            assert exc_info.value.detail == "Custom error message"


class TestCheckSearchSpaceAccess:
    """Tests for check_search_space_access function."""

    @pytest.mark.asyncio
    async def test_member_has_access(self):
        """Test member with any membership has access."""
        mock_membership = MagicMock()
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            result = await check_search_space_access(mock_session, mock_user, 1)
            
            assert result == mock_membership

    @pytest.mark.asyncio
    async def test_no_membership_raises(self):
        """Test user without membership raises HTTPException."""
        with patch("app.utils.rbac.get_user_membership", return_value=None):
            mock_session = AsyncMock()
            mock_user = MagicMock()
            mock_user.id = uuid4()
            
            with pytest.raises(HTTPException) as exc_info:
                await check_search_space_access(mock_session, mock_user, 1)
            
            assert exc_info.value.status_code == 403


class TestIsSearchSpaceOwner:
    """Tests for is_search_space_owner function."""

    @pytest.mark.asyncio
    async def test_returns_true_for_owner(self):
        """Test returns True when user is owner."""
        mock_membership = MagicMock()
        mock_membership.is_owner = True
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            result = await is_search_space_owner(mock_session, user_id, 1)
            
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_owner(self):
        """Test returns False when user is not owner."""
        mock_membership = MagicMock()
        mock_membership.is_owner = False
        
        with patch("app.utils.rbac.get_user_membership", return_value=mock_membership):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            result = await is_search_space_owner(mock_session, user_id, 1)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_no_membership(self):
        """Test returns False when user has no membership."""
        with patch("app.utils.rbac.get_user_membership", return_value=None):
            mock_session = AsyncMock()
            user_id = uuid4()
            
            result = await is_search_space_owner(mock_session, user_id, 1)
            
            assert result is False
