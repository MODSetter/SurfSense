"""Add podcast staleness detection columns

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
    """Add state_version to chats table and chat_state_version to podcasts table."""

    # Add state_version column to chats table with default value of 1
    op.add_column(
        "chats",
        sa.Column("state_version", sa.BigInteger(), nullable=False, server_default="1"),
    )

    # Add chat_state_version column to podcasts table (nullable, set when podcast is generated)
    op.add_column(
        "podcasts", sa.Column("chat_state_version", sa.BigInteger(), nullable=True)
    )


def downgrade() -> None:
    """Remove state_version and chat_state_version columns."""

    # Remove chat_state_version from podcasts table
    op.drop_column("podcasts", "chat_state_version")

    # Remove state_version from chats table
    op.drop_column("chats", "state_version")
