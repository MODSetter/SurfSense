"""Add page limit fields to user table

Revision ID: 33
Revises: 32

Changes:
1. Add pages_limit column (Integer, default 500)
2. Add pages_used column (Integer, default 0)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "33"
down_revision: str | None = "32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add page limit fields to user table."""

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    user_columns = [col["name"] for col in inspector.get_columns("user")]

    # Add pages_limit column if it doesn't exist
    if "pages_limit" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "pages_limit",
                sa.Integer(),
                nullable=False,
                server_default="500",
            ),
        )

    # Add pages_used column if it doesn't exist
    if "pages_used" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "pages_used",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    """Remove page limit fields from user table."""

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    user_columns = [col["name"] for col in inspector.get_columns("user")]

    # Drop columns if they exist
    if "pages_used" in user_columns:
        op.drop_column("user", "pages_used")

    if "pages_limit" in user_columns:
        op.drop_column("user", "pages_limit")
