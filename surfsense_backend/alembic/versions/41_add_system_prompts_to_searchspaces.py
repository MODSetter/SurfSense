"""add_qna_configuration_to_searchspaces

Revision ID: 41
Revises: 40
Create Date: 2025-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "41"
down_revision: str | None = "40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add QnA configuration columns to searchspaces table."""
    # Add citations_enabled boolean (default True)
    op.add_column(
        "searchspaces",
        sa.Column(
            "citations_enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
    )

    # Add custom instructions text field (nullable, defaults to empty)
    op.add_column(
        "searchspaces",
        sa.Column("qna_custom_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove QnA configuration columns from searchspaces table."""
    op.drop_column("searchspaces", "qna_custom_instructions")
    op.drop_column("searchspaces", "citations_enabled")
