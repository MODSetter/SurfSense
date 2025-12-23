"""50_remove_podcast_chat_columns

Revision ID: 50
Revises: 49
Create Date: 2025-12-21

Removes chat_id and chat_state_version columns from podcasts table.
These columns were used for the old chat system podcast linking which
has been replaced by the new-chat content-based podcast generation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50"
down_revision: str | None = "49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Remove chat_id and chat_state_version from podcasts."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("podcasts")]

    if "chat_id" in columns:
        op.drop_column("podcasts", "chat_id")

    if "chat_state_version" in columns:
        op.drop_column("podcasts", "chat_state_version")


def downgrade() -> None:
    """Downgrade schema - Re-add chat_id and chat_state_version to podcasts."""
    op.add_column(
        "podcasts",
        sa.Column("chat_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "podcasts",
        sa.Column("chat_state_version", sa.String(100), nullable=True),
    )
