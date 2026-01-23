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


def downgrade() -> None:
    """Remove public sharing columns from new_chat_threads."""
    op.drop_column("new_chat_threads", "public_share_enabled")
    op.drop_column("new_chat_threads", "public_share_token")
