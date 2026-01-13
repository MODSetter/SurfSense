"""Add podcast staleness detection columns to chats and podcasts tables

This feature allows the system to detect when a podcast is outdated compared to
the current state of the chat it was generated from, enabling users to regenerate
podcasts when needed.

Revision ID: 34
Revises: 33
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "34"
down_revision: str | None = "33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
        ),
        {"table_name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Add columns only if they don't already exist (safe for re-runs)."""

    # Add 'state_version' column to chats table (default 1)
    # Skip if chats table doesn't exist (fresh database)
    if table_exists("chats"):
        op.execute("""
            ALTER TABLE chats
            ADD COLUMN IF NOT EXISTS state_version BIGINT DEFAULT 1 NOT NULL
        """)

    # Add 'chat_state_version' column to podcasts table
    if table_exists("podcasts"):
        op.execute("""
            ALTER TABLE podcasts
            ADD COLUMN IF NOT EXISTS chat_state_version BIGINT
        """)

        # Add 'chat_id' column to podcasts table
        op.execute("""
            ALTER TABLE podcasts
            ADD COLUMN IF NOT EXISTS chat_id INTEGER
        """)


def downgrade() -> None:
    """Remove columns only if they exist."""

    if table_exists("podcasts"):
        op.execute("""
            ALTER TABLE podcasts
            DROP COLUMN IF EXISTS chat_state_version
        """)

        op.execute("""
            ALTER TABLE podcasts
            DROP COLUMN IF EXISTS chat_id
        """)

    if table_exists("chats"):
        op.execute("""
            ALTER TABLE chats
            DROP COLUMN IF EXISTS state_version
        """)
