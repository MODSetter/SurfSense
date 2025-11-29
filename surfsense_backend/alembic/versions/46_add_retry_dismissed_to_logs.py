"""Add retry_count and DISMISSED status to logs

Revision ID: 46
Revises: 45

Changes:
1. Add retry_count column to logs table
2. Add DISMISSED to LogStatus enum
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "46"
down_revision: str | None = "45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add retry_count column and DISMISSED status to logs."""
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    log_columns = [col["name"] for col in inspector.get_columns("logs")]

    # Add retry_count column if it doesn't exist
    if "retry_count" not in log_columns:
        op.add_column(
            "logs",
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    # Update LogStatus enum to include DISMISSED
    # PostgreSQL requires explicit type modification
    op.execute(
        """
        ALTER TYPE logstatus ADD VALUE IF NOT EXISTS 'DISMISSED'
        """
    )


def downgrade() -> None:
    """Remove retry_count column (note: enum values cannot be removed in PostgreSQL)."""
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    log_columns = [col["name"] for col in inspector.get_columns("logs")]

    # Drop retry_count column if it exists
    if "retry_count" in log_columns:
        op.drop_column("logs", "retry_count")

    # Note: PostgreSQL does not support removing enum values
    # The DISMISSED value will remain in the enum even after downgrade
