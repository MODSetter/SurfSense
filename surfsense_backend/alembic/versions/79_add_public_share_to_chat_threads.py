"""Add public sharing columns to new_chat_threads

Revision ID: 79
Revises: 78
Create Date: 2026-01-23

Adds public_share_token and public_share_enabled columns to enable
public sharing of chat threads via secure tokenized URLs.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "79"
down_revision: str | None = "78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add public sharing columns to new_chat_threads."""
    # Add public_share_token column
    op.add_column(
        "new_chat_threads",
        sa.Column("public_share_token", sa.String(64), nullable=True),
    )

    # Add public_share_enabled column
    op.add_column(
        "new_chat_threads",
        sa.Column(
            "public_share_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Add unique partial index on public_share_token (only non-null values)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_new_chat_threads_public_share_token
        ON new_chat_threads(public_share_token)
        WHERE public_share_token IS NOT NULL
        """
    )

    # Add partial index on public_share_enabled for fast public chat queries
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_public_share_enabled
        ON new_chat_threads(public_share_enabled)
        WHERE public_share_enabled = TRUE
        """
    )


def downgrade() -> None:
    """Remove public sharing columns from new_chat_threads."""
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_public_share_enabled")
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_public_share_token")
    op.drop_column("new_chat_threads", "public_share_enabled")
    op.drop_column("new_chat_threads", "public_share_token")
