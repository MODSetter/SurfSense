"""Add periodic indexing fields to search_source_connectors

Revision ID: 32
Revises: 31

Changes:
1. Add periodic_indexing_enabled column (Boolean, default False)
2. Add indexing_frequency_minutes column (Integer, nullable)
3. Add next_scheduled_at column (TIMESTAMP with timezone, nullable)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32"
down_revision: str | None = "31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add periodic indexing fields to search_source_connectors table."""

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    connector_columns = [
        col["name"] for col in inspector.get_columns("search_source_connectors")
    ]

    # Add periodic_indexing_enabled column if it doesn't exist
    if "periodic_indexing_enabled" not in connector_columns:
        op.add_column(
            "search_source_connectors",
            sa.Column(
                "periodic_indexing_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
        )

    # Add indexing_frequency_minutes column if it doesn't exist
    if "indexing_frequency_minutes" not in connector_columns:
        op.add_column(
            "search_source_connectors",
            sa.Column(
                "indexing_frequency_minutes",
                sa.Integer(),
                nullable=True,
            ),
        )

    # Add next_scheduled_at column if it doesn't exist
    if "next_scheduled_at" not in connector_columns:
        op.add_column(
            "search_source_connectors",
            sa.Column(
                "next_scheduled_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Remove periodic indexing fields from search_source_connectors table."""

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    connector_columns = [
        col["name"] for col in inspector.get_columns("search_source_connectors")
    ]

    # Drop columns if they exist
    if "next_scheduled_at" in connector_columns:
        op.drop_column("search_source_connectors", "next_scheduled_at")

    if "indexing_frequency_minutes" in connector_columns:
        op.drop_column("search_source_connectors", "indexing_frequency_minutes")

    if "periodic_indexing_enabled" in connector_columns:
        op.drop_column("search_source_connectors", "periodic_indexing_enabled")
