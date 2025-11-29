"""add_qna_configuration_to_searchspaces

Revision ID: 37
Revises: 36
Create Date: 2025-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37"
down_revision: str | None = "36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists on the given table."""
    result = connection.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Add QnA configuration columns to searchspaces table."""
    connection = op.get_bind()

    # Add citations_enabled boolean (default True)
    if not column_exists(connection, "searchspaces", "citations_enabled"):
        op.add_column(
            "searchspaces",
            sa.Column(
                "citations_enabled", sa.Boolean(), nullable=False, server_default="true"
            ),
        )
    else:
        print("Column 'citations_enabled' already exists. Skipping.")

    # Add custom instructions text field (nullable, defaults to empty)
    if not column_exists(connection, "searchspaces", "qna_custom_instructions"):
        op.add_column(
            "searchspaces",
            sa.Column("qna_custom_instructions", sa.Text(), nullable=True),
        )
    else:
        print("Column 'qna_custom_instructions' already exists. Skipping.")


def downgrade() -> None:
    """Remove QnA configuration columns from searchspaces table."""
    connection = op.get_bind()

    if column_exists(connection, "searchspaces", "qna_custom_instructions"):
        op.drop_column("searchspaces", "qna_custom_instructions")
    else:
        print("Column 'qna_custom_instructions' does not exist. Skipping.")

    if column_exists(connection, "searchspaces", "citations_enabled"):
        op.drop_column("searchspaces", "citations_enabled")
    else:
        print("Column 'citations_enabled' does not exist. Skipping.")
