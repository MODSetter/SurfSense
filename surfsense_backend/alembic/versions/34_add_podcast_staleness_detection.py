"""Add podcast staleness detection columns to chats and podcasts tables

This feature allows the system to detect when a podcast is outdated compared to
the current state of the chat it was generated from, enabling users to regenerate
podcasts when needed.

Revision ID: 34
Revises: 33
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers
revision: str = "34"
down_revision: str | None = "33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add columns only if they don't already exist (safe for re-runs)."""

    # Add 'state_version' column to chats table (default 1)
    op.execute("""
        ALTER TABLE chats
        ADD COLUMN IF NOT EXISTS state_version BIGINT DEFAULT 1 NOT NULL
    """)

    # Add 'chat_state_version' column to podcasts table
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

    op.execute("""
        ALTER TABLE podcasts
        DROP COLUMN IF EXISTS chat_state_version
    """)

    op.execute("""
        ALTER TABLE podcasts
        DROP COLUMN IF EXISTS chat_id
    """)

    op.execute("""
        ALTER TABLE chats
        DROP COLUMN IF EXISTS state_version
    """)
