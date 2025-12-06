"""
Tests for permission functions in db.py.

This module tests the permission checking functions used in RBAC.
"""

from app.db import (
    DEFAULT_ROLE_PERMISSIONS,
    Permission,
    get_default_roles_config,
    has_all_permissions,
    has_any_permission,
    has_permission,
)


class TestHasPermission:
    """Tests for has_permission function."""

    def test_has_permission_with_exact_match(self):
        """Test has_permission returns True for exact permission match."""
        permissions = [Permission.DOCUMENTS_READ.value, Permission.CHATS_READ.value]
        assert has_permission(permissions, Permission.DOCUMENTS_READ.value) is True

    def test_has_permission_with_no_match(self):
        """Test has_permission returns False when permission not in list."""
        permissions = [Permission.DOCUMENTS_READ.value]
        assert has_permission(permissions, Permission.DOCUMENTS_CREATE.value) is False

    def test_has_permission_with_full_access(self):
        """Test has_permission returns True for any permission when user has FULL_ACCESS."""
        permissions = [Permission.FULL_ACCESS.value]
        assert has_permission(permissions, Permission.DOCUMENTS_CREATE.value) is True
        assert has_permission(permissions, Permission.SETTINGS_DELETE.value) is True
        assert has_permission(permissions, Permission.MEMBERS_MANAGE_ROLES.value) is True

    def test_has_permission_with_empty_list(self):
        """Test has_permission returns False for empty permission list."""
        assert has_permission([], Permission.DOCUMENTS_READ.value) is False

    def test_has_permission_with_none(self):
        """Test has_permission returns False for None."""
        assert has_permission(None, Permission.DOCUMENTS_READ.value) is False


class TestHasAnyPermission:
    """Tests for has_any_permission function."""

    def test_has_any_permission_with_one_match(self):
        """Test has_any_permission returns True when at least one permission matches."""
        user_permissions = [Permission.DOCUMENTS_READ.value, Permission.CHATS_READ.value]
        required = [Permission.DOCUMENTS_READ.value, Permission.DOCUMENTS_CREATE.value]
        assert has_any_permission(user_permissions, required) is True

    def test_has_any_permission_with_all_match(self):
        """Test has_any_permission returns True when all permissions match."""
        user_permissions = [Permission.DOCUMENTS_READ.value, Permission.CHATS_READ.value]
        required = [Permission.DOCUMENTS_READ.value, Permission.CHATS_READ.value]
        assert has_any_permission(user_permissions, required) is True

    def test_has_any_permission_with_no_match(self):
        """Test has_any_permission returns False when no permissions match."""
        user_permissions = [Permission.DOCUMENTS_READ.value]
        required = [Permission.CHATS_CREATE.value, Permission.SETTINGS_UPDATE.value]
        assert has_any_permission(user_permissions, required) is False

    def test_has_any_permission_with_full_access(self):
        """Test has_any_permission returns True with FULL_ACCESS."""
        user_permissions = [Permission.FULL_ACCESS.value]
        required = [Permission.SETTINGS_DELETE.value]
        assert has_any_permission(user_permissions, required) is True

    def test_has_any_permission_with_empty_user_permissions(self):
        """Test has_any_permission returns False with empty user permissions."""
        assert has_any_permission([], [Permission.DOCUMENTS_READ.value]) is False

    def test_has_any_permission_with_none(self):
        """Test has_any_permission returns False with None."""
        assert has_any_permission(None, [Permission.DOCUMENTS_READ.value]) is False


class TestHasAllPermissions:
    """Tests for has_all_permissions function."""

    def test_has_all_permissions_with_all_match(self):
        """Test has_all_permissions returns True when all permissions match."""
        user_permissions = [
            Permission.DOCUMENTS_READ.value,
            Permission.DOCUMENTS_CREATE.value,
            Permission.CHATS_READ.value,
        ]
        required = [Permission.DOCUMENTS_READ.value, Permission.DOCUMENTS_CREATE.value]
        assert has_all_permissions(user_permissions, required) is True

    def test_has_all_permissions_with_partial_match(self):
        """Test has_all_permissions returns False when only some permissions match."""
        user_permissions = [Permission.DOCUMENTS_READ.value]
        required = [Permission.DOCUMENTS_READ.value, Permission.DOCUMENTS_CREATE.value]
        assert has_all_permissions(user_permissions, required) is False

    def test_has_all_permissions_with_no_match(self):
        """Test has_all_permissions returns False when no permissions match."""
        user_permissions = [Permission.CHATS_READ.value]
        required = [Permission.DOCUMENTS_READ.value, Permission.DOCUMENTS_CREATE.value]
        assert has_all_permissions(user_permissions, required) is False

    def test_has_all_permissions_with_full_access(self):
        """Test has_all_permissions returns True with FULL_ACCESS."""
        user_permissions = [Permission.FULL_ACCESS.value]
        required = [
            Permission.DOCUMENTS_READ.value,
            Permission.DOCUMENTS_CREATE.value,
            Permission.SETTINGS_DELETE.value,
        ]
        assert has_all_permissions(user_permissions, required) is True

    def test_has_all_permissions_with_empty_user_permissions(self):
        """Test has_all_permissions returns False with empty user permissions."""
        assert has_all_permissions([], [Permission.DOCUMENTS_READ.value]) is False

    def test_has_all_permissions_with_none(self):
        """Test has_all_permissions returns False with None."""
        assert has_all_permissions(None, [Permission.DOCUMENTS_READ.value]) is False

    def test_has_all_permissions_with_empty_required(self):
        """Test has_all_permissions returns True with empty required list."""
        user_permissions = [Permission.DOCUMENTS_READ.value]
        assert has_all_permissions(user_permissions, []) is True


class TestPermissionEnum:
    """Tests for Permission enum values."""

    def test_permission_values_are_strings(self):
        """Test all permission values are strings."""
        for perm in list(Permission):
            assert isinstance(perm.value, str)

    def test_permission_document_values(self):
        """Test document permission values."""
        assert Permission.DOCUMENTS_CREATE.value == "documents:create"
        assert Permission.DOCUMENTS_READ.value == "documents:read"
        assert Permission.DOCUMENTS_UPDATE.value == "documents:update"
        assert Permission.DOCUMENTS_DELETE.value == "documents:delete"

    def test_permission_chat_values(self):
        """Test chat permission values."""
        assert Permission.CHATS_CREATE.value == "chats:create"
        assert Permission.CHATS_READ.value == "chats:read"
        assert Permission.CHATS_UPDATE.value == "chats:update"
        assert Permission.CHATS_DELETE.value == "chats:delete"

    def test_permission_llm_config_values(self):
        """Test LLM config permission values."""
        assert Permission.LLM_CONFIGS_CREATE.value == "llm_configs:create"
        assert Permission.LLM_CONFIGS_READ.value == "llm_configs:read"
        assert Permission.LLM_CONFIGS_UPDATE.value == "llm_configs:update"
        assert Permission.LLM_CONFIGS_DELETE.value == "llm_configs:delete"

    def test_permission_members_values(self):
        """Test member permission values."""
        assert Permission.MEMBERS_INVITE.value == "members:invite"
        assert Permission.MEMBERS_VIEW.value == "members:view"
        assert Permission.MEMBERS_REMOVE.value == "members:remove"
        assert Permission.MEMBERS_MANAGE_ROLES.value == "members:manage_roles"

    def test_permission_full_access_value(self):
        """Test FULL_ACCESS permission value."""
        assert Permission.FULL_ACCESS.value == "*"


class TestDefaultRolePermissions:
    """Tests for DEFAULT_ROLE_PERMISSIONS configuration."""

    def test_owner_has_full_access(self):
        """Test Owner role has full access."""
        assert Permission.FULL_ACCESS.value in DEFAULT_ROLE_PERMISSIONS["Owner"]

    def test_admin_permissions(self):
        """Test Admin role has appropriate permissions."""
        admin_perms = DEFAULT_ROLE_PERMISSIONS["Admin"]
        # Admin should have document permissions
        assert Permission.DOCUMENTS_CREATE.value in admin_perms
        assert Permission.DOCUMENTS_READ.value in admin_perms
        assert Permission.DOCUMENTS_UPDATE.value in admin_perms
        assert Permission.DOCUMENTS_DELETE.value in admin_perms
        # Admin should NOT have settings:delete
        assert Permission.SETTINGS_DELETE.value not in admin_perms

    def test_editor_permissions(self):
        """Test Editor role has appropriate permissions."""
        editor_perms = DEFAULT_ROLE_PERMISSIONS["Editor"]
        # Editor should have document CRUD
        assert Permission.DOCUMENTS_CREATE.value in editor_perms
        assert Permission.DOCUMENTS_READ.value in editor_perms
        assert Permission.DOCUMENTS_UPDATE.value in editor_perms
        assert Permission.DOCUMENTS_DELETE.value in editor_perms
        # Editor should have chat CRUD
        assert Permission.CHATS_CREATE.value in editor_perms
        assert Permission.CHATS_READ.value in editor_perms
        # Editor should NOT have member management
        assert Permission.MEMBERS_REMOVE.value not in editor_perms

    def test_viewer_permissions(self):
        """Test Viewer role has read-only permissions."""
        viewer_perms = DEFAULT_ROLE_PERMISSIONS["Viewer"]
        # Viewer should have read permissions
        assert Permission.DOCUMENTS_READ.value in viewer_perms
        assert Permission.CHATS_READ.value in viewer_perms
        assert Permission.LLM_CONFIGS_READ.value in viewer_perms
        # Viewer should NOT have create/update/delete permissions
        assert Permission.DOCUMENTS_CREATE.value not in viewer_perms
        assert Permission.DOCUMENTS_UPDATE.value not in viewer_perms
        assert Permission.DOCUMENTS_DELETE.value not in viewer_perms
        assert Permission.CHATS_CREATE.value not in viewer_perms


class TestGetDefaultRolesConfig:
    """Tests for get_default_roles_config function."""

    def test_returns_list(self):
        """Test get_default_roles_config returns a list."""
        config = get_default_roles_config()
        assert isinstance(config, list)

    def test_contains_four_roles(self):
        """Test get_default_roles_config returns 4 roles."""
        config = get_default_roles_config()
        assert len(config) == 4

    def test_role_names(self):
        """Test get_default_roles_config contains expected role names."""
        config = get_default_roles_config()
        role_names = [role["name"] for role in config]
        assert "Owner" in role_names
        assert "Admin" in role_names
        assert "Editor" in role_names
        assert "Viewer" in role_names

    def test_all_roles_are_system_roles(self):
        """Test all default roles are system roles."""
        config = get_default_roles_config()
        for role in config:
            assert role["is_system_role"] is True

    def test_editor_is_default_role(self):
        """Test Editor is the default role for new members."""
        config = get_default_roles_config()
        editor_role = next(role for role in config if role["name"] == "Editor")
        assert editor_role["is_default"] is True

    def test_owner_is_not_default_role(self):
        """Test Owner is not the default role."""
        config = get_default_roles_config()
        owner_role = next(role for role in config if role["name"] == "Owner")
        assert owner_role["is_default"] is False

    def test_role_structure(self):
        """Test each role has required fields."""
        config = get_default_roles_config()
        required_fields = ["name", "description", "permissions", "is_default", "is_system_role"]
        for role in config:
            for field in required_fields:
                assert field in role, f"Role {role.get('name')} missing field {field}"

    def test_owner_role_permissions(self):
        """Test Owner role has full access permission."""
        config = get_default_roles_config()
        owner_role = next(role for role in config if role["name"] == "Owner")
        assert Permission.FULL_ACCESS.value in owner_role["permissions"]
