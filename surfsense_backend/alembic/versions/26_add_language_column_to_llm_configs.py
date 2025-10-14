"""Add language column to llm_configs

Revision ID: 26
Revises: 25

Changes:
1. Add language column to llm_configs table with default value of 'English'
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26"
down_revision: str | None = "25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add language column to llm_configs table."""

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    llm_config_columns = [col["name"] for col in inspector.get_columns("llm_configs")]

    # Add language column if it doesn't exist
    if "language" not in llm_config_columns:
        op.add_column(
            "llm_configs",
            sa.Column(
                "language",
                sa.String(length=50),
                nullable=True,
                server_default="English",
            ),
        )

        # Update existing rows to have 'English' as default
        op.execute(
            """
            UPDATE llm_configs
            SET language = 'English'
            WHERE language IS NULL
            """
        )


def downgrade() -> None:
    """Remove language column from llm_configs table."""

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    llm_config_columns = [col["name"] for col in inspector.get_columns("llm_configs")]

    # Drop language column if it exists
    if "language" in llm_config_columns:
        op.drop_column("llm_configs", "language")
