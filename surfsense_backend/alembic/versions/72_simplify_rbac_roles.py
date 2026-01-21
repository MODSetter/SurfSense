"""Simplify RBAC roles - Remove Admin role, keep only Owner, Editor, Viewer

Revision ID: 72
Revises: 71
Create Date: 2025-01-20

This migration:
1. Moves any users with Admin role to Editor role
2. Updates invites that reference Admin role to use Editor role
3. Deletes the Admin role from all search spaces
4. Updates Editor permissions to the new simplified set (everything except delete)
5. Updates Viewer permissions to the new simplified set (read-only + comments)
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "72"
down_revision = "71"
branch_labels = None
depends_on = None

# New Editor permissions (can do everything except delete, manage roles, and update settings)
NEW_EDITOR_PERMISSIONS = [
    "documents:create",
    "documents:read",
    "documents:update",
    "chats:create",
    "chats:read",
    "chats:update",
    "comments:create",
    "comments:read",
    "llm_configs:create",
    "llm_configs:read",
    "llm_configs:update",
    "podcasts:create",
    "podcasts:read",
    "podcasts:update",
    "connectors:create",
    "connectors:read",
    "connectors:update",
    "logs:read",
    "members:invite",
    "members:view",
    "roles:read",
    "settings:view",
]

# New Viewer permissions (read-only + comments)
NEW_VIEWER_PERMISSIONS = [
    "documents:read",
    "chats:read",
    "comments:create",
    "comments:read",
    "llm_configs:read",
    "podcasts:read",
    "connectors:read",
    "logs:read",
    "members:view",
    "roles:read",
    "settings:view",
]


def upgrade():
    connection = op.get_bind()

    # Step 1: Move all memberships from Admin roles to corresponding Editor roles (BULK)
    # Uses a subquery to match Admin->Editor within the same search space
    connection.execute(
        sa.text("""
            UPDATE search_space_memberships m
            SET role_id = e.id
            FROM search_space_roles a
            JOIN search_space_roles e ON a.search_space_id = e.search_space_id
            WHERE m.role_id = a.id
            AND a.name = 'Admin'
            AND e.name = 'Editor'
        """)
    )

    # Step 2: Move all invites from Admin roles to corresponding Editor roles (BULK)
    connection.execute(
        sa.text("""
            UPDATE search_space_invites i
            SET role_id = e.id
            FROM search_space_roles a
            JOIN search_space_roles e ON a.search_space_id = e.search_space_id
            WHERE i.role_id = a.id
            AND a.name = 'Admin'
            AND e.name = 'Editor'
        """)
    )

    # Step 3: Delete all Admin roles (BULK)
    connection.execute(
        sa.text("""
            DELETE FROM search_space_roles 
            WHERE name = 'Admin' AND is_system_role = TRUE
        """)
    )

    # Step 4: Update Editor permissions for all search spaces (BULK)
    editor_perms_literal = (
        "ARRAY[" + ",".join(f"'{p}'" for p in NEW_EDITOR_PERMISSIONS) + "]::TEXT[]"
    )
    connection.execute(
        sa.text(f"""
            UPDATE search_space_roles 
            SET permissions = {editor_perms_literal},
                description = 'Can create and update content (no delete, role management, or settings access)'
            WHERE name = 'Editor' AND is_system_role = TRUE
        """)
    )

    # Step 5: Update Viewer permissions for all search spaces (BULK)
    viewer_perms_literal = (
        "ARRAY[" + ",".join(f"'{p}'" for p in NEW_VIEWER_PERMISSIONS) + "]::TEXT[]"
    )
    connection.execute(
        sa.text(f"""
            UPDATE search_space_roles 
            SET permissions = {viewer_perms_literal}
            WHERE name = 'Viewer' AND is_system_role = TRUE
        """)
    )


def downgrade():
    """
    Downgrade recreates the Admin role and restores original permissions.
    Note: Users who were moved from Admin to Editor will remain as Editor.
    """
    connection = op.get_bind()

    # Old Admin permissions
    old_admin_permissions = [
        "documents:create",
        "documents:read",
        "documents:update",
        "documents:delete",
        "chats:create",
        "chats:read",
        "chats:update",
        "chats:delete",
        "comments:create",
        "comments:read",
        "comments:delete",
        "llm_configs:create",
        "llm_configs:read",
        "llm_configs:update",
        "llm_configs:delete",
        "podcasts:create",
        "podcasts:read",
        "podcasts:update",
        "podcasts:delete",
        "connectors:create",
        "connectors:read",
        "connectors:update",
        "connectors:delete",
        "logs:read",
        "logs:delete",
        "members:invite",
        "members:view",
        "members:remove",
        "members:manage_roles",
        "roles:create",
        "roles:read",
        "roles:update",
        "roles:delete",
        "settings:view",
        "settings:update",
    ]

    # Old Editor permissions
    old_editor_permissions = [
        "documents:create",
        "documents:read",
        "documents:update",
        "documents:delete",
        "chats:create",
        "chats:read",
        "chats:update",
        "chats:delete",
        "comments:create",
        "comments:read",
        "llm_configs:read",
        "llm_configs:create",
        "llm_configs:update",
        "podcasts:create",
        "podcasts:read",
        "podcasts:update",
        "podcasts:delete",
        "connectors:create",
        "connectors:read",
        "connectors:update",
        "logs:read",
        "members:view",
        "roles:read",
        "settings:view",
    ]

    # Old Viewer permissions
    old_viewer_permissions = [
        "documents:read",
        "chats:read",
        "comments:create",
        "comments:read",
        "llm_configs:read",
        "podcasts:read",
        "connectors:read",
        "logs:read",
        "members:view",
        "roles:read",
        "settings:view",
    ]

    # Recreate Admin role for each search space
    search_spaces = connection.execute(
        sa.text("SELECT id FROM searchspaces")
    ).fetchall()

    admin_perms_literal = (
        "ARRAY[" + ",".join(f"'{p}'" for p in old_admin_permissions) + "]::TEXT[]"
    )

    for (ss_id,) in search_spaces:
        # Check if Admin role already exists
        existing = connection.execute(
            sa.text("""
                SELECT id FROM search_space_roles 
                WHERE search_space_id = :ss_id AND name = 'Admin'
            """),
            {"ss_id": ss_id},
        ).fetchone()

        if not existing:
            connection.execute(
                sa.text(f"""
                    INSERT INTO search_space_roles 
                    (name, description, permissions, is_default, is_system_role, search_space_id)
                    VALUES (
                        'Admin',
                        'Can manage most resources except deleting the search space',
                        {admin_perms_literal},
                        FALSE,
                        TRUE,
                        :ss_id
                    )
                """),
                {"ss_id": ss_id},
            )

    # Restore old Editor permissions
    editor_perms_literal = (
        "ARRAY[" + ",".join(f"'{p}'" for p in old_editor_permissions) + "]::TEXT[]"
    )
    connection.execute(
        sa.text(f"""
            UPDATE search_space_roles 
            SET permissions = {editor_perms_literal},
                description = 'Can create and edit documents, chats, and podcasts'
            WHERE name = 'Editor' AND is_system_role = TRUE
        """)
    )

    # Restore old Viewer permissions
    viewer_perms_literal = (
        "ARRAY[" + ",".join(f"'{p}'" for p in old_viewer_permissions) + "]::TEXT[]"
    )
    connection.execute(
        sa.text(f"""
            UPDATE search_space_roles 
            SET permissions = {viewer_perms_literal}
            WHERE name = 'Viewer' AND is_system_role = TRUE
        """)
    )
