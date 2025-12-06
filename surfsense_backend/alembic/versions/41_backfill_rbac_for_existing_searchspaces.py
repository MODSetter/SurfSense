"""Backfill RBAC data for existing search spaces

Revision ID: 41
Revises: 40
Create Date: 2025-11-28

This migration creates default roles and owner memberships for all existing
search spaces that were created before the RBAC system was implemented.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "41"
down_revision = "40"
branch_labels = None
depends_on = None

# Default role permissions (must match DEFAULT_ROLE_PERMISSIONS in db.py)
DEFAULT_ROLES = [
    {
        "name": "Owner",
        "description": "Full access to all resources",
        "permissions": ["*"],
        "is_system_role": True,
        "is_default": False,
    },
    {
        "name": "Admin",
        "description": "Can manage members, roles, and all content",
        "permissions": [
            "documents:create",
            "documents:read",
            "documents:update",
            "documents:delete",
            "chats:create",
            "chats:read",
            "chats:update",
            "chats:delete",
            "llm_configs:create",
            "llm_configs:read",
            "llm_configs:update",
            "llm_configs:delete",
            "logs:read",
            "logs:delete",
            "podcasts:create",
            "podcasts:read",
            "podcasts:update",
            "podcasts:delete",
            "connectors:create",
            "connectors:read",
            "connectors:update",
            "connectors:delete",
            "members:read",
            "members:update",
            "members:delete",
            "roles:create",
            "roles:read",
            "roles:update",
            "roles:delete",
            "invites:create",
            "invites:read",
            "invites:delete",
            "settings:read",
            "settings:update",
        ],
        "is_system_role": True,
        "is_default": False,
    },
    {
        "name": "Editor",
        "description": "Can create and edit content",
        "permissions": [
            "documents:create",
            "documents:read",
            "documents:update",
            "chats:create",
            "chats:read",
            "chats:update",
            "llm_configs:read",
            "logs:read",
            "podcasts:create",
            "podcasts:read",
            "podcasts:update",
            "connectors:create",
            "connectors:read",
            "connectors:update",
            "members:read",
            "roles:read",
        ],
        "is_system_role": True,
        "is_default": True,
    },
    {
        "name": "Viewer",
        "description": "Read-only access to content",
        "permissions": [
            "documents:read",
            "chats:read",
            "llm_configs:read",
            "logs:read",
            "podcasts:read",
            "connectors:read",
            "members:read",
            "roles:read",
        ],
        "is_system_role": True,
        "is_default": False,
    },
]


def upgrade():
    connection = op.get_bind()

    # Get all existing search spaces that don't have roles yet
    search_spaces = connection.execute(
        sa.text("""
            SELECT ss.id, ss.user_id 
            FROM searchspaces ss
            WHERE NOT EXISTS (
                SELECT 1 FROM search_space_roles ssr 
                WHERE ssr.search_space_id = ss.id
            )
        """)
    ).fetchall()

    for ss_id, owner_user_id in search_spaces:
        owner_role_id = None

        # Create default roles for each search space
        for role in DEFAULT_ROLES:
            # Convert permissions list to PostgreSQL array literal format for raw SQL
            perms_literal = (
                "ARRAY[" + ",".join(f"'{p}'" for p in role["permissions"]) + "]::TEXT[]"
            )

            result = connection.execute(
                sa.text(f"""
                    INSERT INTO search_space_roles 
                    (name, description, permissions, is_default, is_system_role, search_space_id)
                    VALUES (:name, :description, {perms_literal}, :is_default, :is_system_role, :search_space_id)
                    RETURNING id
                """),
                {
                    "name": role["name"],
                    "description": role["description"],
                    "is_default": role["is_default"],
                    "is_system_role": role["is_system_role"],
                    "search_space_id": ss_id,
                },
            )
            role_id = result.fetchone()[0]

            # Keep track of Owner role ID
            if role["name"] == "Owner":
                owner_role_id = role_id

        # Create owner membership for the search space creator
        if owner_user_id and owner_role_id:
            # Check if membership already exists
            existing = connection.execute(
                sa.text("""
                    SELECT 1 FROM search_space_memberships 
                    WHERE user_id = :user_id AND search_space_id = :search_space_id
                """),
                {"user_id": owner_user_id, "search_space_id": ss_id},
            ).fetchone()

            if not existing:
                connection.execute(
                    sa.text("""
                        INSERT INTO search_space_memberships 
                        (user_id, search_space_id, role_id, is_owner)
                        VALUES (:user_id, :search_space_id, :role_id, TRUE)
                    """),
                    {
                        "user_id": owner_user_id,
                        "search_space_id": ss_id,
                        "role_id": owner_role_id,
                    },
                )


def downgrade():
    # This migration only adds data, not schema changes
    # Downgrade would remove all roles and memberships created by this migration
    # However, this is destructive and may affect manually created data
    # So we only remove system roles and owner memberships that were auto-created
    connection = op.get_bind()

    # Remove memberships where user is owner and role is system Owner role
    connection.execute(
        sa.text("""
            DELETE FROM search_space_memberships ssm
            USING search_space_roles ssr
            WHERE ssm.role_id = ssr.id
            AND ssm.is_owner = TRUE
            AND ssr.is_system_role = TRUE
            AND ssr.name = 'Owner'
        """)
    )

    # Remove system roles
    connection.execute(
        sa.text("""
            DELETE FROM search_space_roles
            WHERE is_system_role = TRUE
        """)
    )
