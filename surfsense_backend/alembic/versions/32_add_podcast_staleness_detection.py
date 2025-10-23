"""Add podcast staleness detection columns to chats and podcasts tables

This feature allows the system to detect when a podcast is outdated compared to the current state of the chat it was generated from, enabling users to regenerate podcasts when needed.

Revision ID: 32
Revises: 31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "32"
down_revision: str | None = "31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add state_version, chat_state_version, and chat_id to chats and podcasts tables."""

    # Add state_version column to chats table with default value of 1
    op.add_column(
        "chats",
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default="1"),
    )

    # Add chat_state_version column to podcasts table (nullable, set when podcast is generated)
    op.add_column(
        "podcasts", sa.Column("chat_state_version", sa.BigInteger(), nullable=True)
    )

    # Add chat_id column to podcasts table (nullable, set when podcast is generated from a chat)
    op.add_column("podcasts", sa.Column("chat_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove state_version, chat_state_version, and chat_id columns."""

    # Remove chat_state_version from podcasts table
    op.drop_column("podcasts", "chat_state_version")

    # Remove chat_id from podcasts table
    op.drop_column("podcasts", "chat_id")

    # Remove state_version from chats table
    op.drop_column("chats", "state_version")
