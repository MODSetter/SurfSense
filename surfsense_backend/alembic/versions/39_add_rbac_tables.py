"""Add RBAC tables for search space access control

Revision ID: 39
Revises: 38
Create Date: 2025-11-27 00:00:00.000000

This migration adds:
- Permission enum for granular access control
- search_space_roles table for custom roles per search space
- search_space_memberships table for user-searchspace-role relationships
- search_space_invites table for invite links
"""

from collections.abc import Sequence

from sqlalchemy import inspect

from alembic import op

revision: str = "39"
down_revision: str | None = "38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add RBAC tables for search space access control."""

    # Create search_space_roles table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_space_roles (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            name VARCHAR(100) NOT NULL,
            description VARCHAR(500),
            permissions TEXT[] NOT NULL DEFAULT '{}',
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
            CONSTRAINT uq_searchspace_role_name UNIQUE (search_space_id, name)
        );
    """
    )

    # Create search_space_invites table (needs to be created before memberships due to FK)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_space_invites (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            invite_code VARCHAR(64) NOT NULL UNIQUE,
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES search_space_roles(id) ON DELETE SET NULL,
            created_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            expires_at TIMESTAMPTZ,
            max_uses INTEGER,
            uses_count INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            name VARCHAR(100)
        );
    """
    )

    # Create search_space_memberships table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_space_memberships (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES search_space_roles(id) ON DELETE SET NULL,
            is_owner BOOLEAN NOT NULL DEFAULT FALSE,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            invited_by_invite_id INTEGER REFERENCES search_space_invites(id) ON DELETE SET NULL,
            CONSTRAINT uq_user_searchspace_membership UNIQUE (user_id, search_space_id)
        );
    """
    )

    # Get connection and inspector for checking existing indexes
    conn = op.get_bind()
    inspector = inspect(conn)

    # Create indexes for search_space_roles
    existing_indexes = [
        idx["name"] for idx in inspector.get_indexes("search_space_roles")
    ]
    if "ix_search_space_roles_id" not in existing_indexes:
        op.create_index("ix_search_space_roles_id", "search_space_roles", ["id"])
    if "ix_search_space_roles_created_at" not in existing_indexes:
        op.create_index(
            "ix_search_space_roles_created_at", "search_space_roles", ["created_at"]
        )
    if "ix_search_space_roles_name" not in existing_indexes:
        op.create_index("ix_search_space_roles_name", "search_space_roles", ["name"])

    # Create indexes for search_space_memberships
    existing_indexes = [
        idx["name"] for idx in inspector.get_indexes("search_space_memberships")
    ]
    if "ix_search_space_memberships_id" not in existing_indexes:
        op.create_index(
            "ix_search_space_memberships_id", "search_space_memberships", ["id"]
        )
    if "ix_search_space_memberships_created_at" not in existing_indexes:
        op.create_index(
            "ix_search_space_memberships_created_at",
            "search_space_memberships",
            ["created_at"],
        )
    if "ix_search_space_memberships_user_id" not in existing_indexes:
        op.create_index(
            "ix_search_space_memberships_user_id",
            "search_space_memberships",
            ["user_id"],
        )
    if "ix_search_space_memberships_search_space_id" not in existing_indexes:
        op.create_index(
            "ix_search_space_memberships_search_space_id",
            "search_space_memberships",
            ["search_space_id"],
        )

    # Create indexes for search_space_invites
    existing_indexes = [
        idx["name"] for idx in inspector.get_indexes("search_space_invites")
    ]
    if "ix_search_space_invites_id" not in existing_indexes:
        op.create_index("ix_search_space_invites_id", "search_space_invites", ["id"])
    if "ix_search_space_invites_created_at" not in existing_indexes:
        op.create_index(
            "ix_search_space_invites_created_at", "search_space_invites", ["created_at"]
        )
    if "ix_search_space_invites_invite_code" not in existing_indexes:
        op.create_index(
            "ix_search_space_invites_invite_code",
            "search_space_invites",
            ["invite_code"],
        )


def downgrade() -> None:
    """Downgrade schema - remove RBAC tables."""

    # Drop indexes for search_space_memberships
    op.drop_index(
        "ix_search_space_memberships_search_space_id",
        table_name="search_space_memberships",
    )
    op.drop_index(
        "ix_search_space_memberships_user_id", table_name="search_space_memberships"
    )
    op.drop_index(
        "ix_search_space_memberships_created_at", table_name="search_space_memberships"
    )
    op.drop_index(
        "ix_search_space_memberships_id", table_name="search_space_memberships"
    )

    # Drop indexes for search_space_invites
    op.drop_index(
        "ix_search_space_invites_invite_code", table_name="search_space_invites"
    )
    op.drop_index(
        "ix_search_space_invites_created_at", table_name="search_space_invites"
    )
    op.drop_index("ix_search_space_invites_id", table_name="search_space_invites")

    # Drop indexes for search_space_roles
    op.drop_index("ix_search_space_roles_name", table_name="search_space_roles")
    op.drop_index("ix_search_space_roles_created_at", table_name="search_space_roles")
    op.drop_index("ix_search_space_roles_id", table_name="search_space_roles")

    # Drop tables in correct order (respecting foreign key constraints)
    op.drop_table("search_space_memberships")
    op.drop_table("search_space_invites")
    op.drop_table("search_space_roles")
