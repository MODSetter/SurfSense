"""Remove is_generated column from podcasts table

Revision ID: 7
Revises: 6

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7"
down_revision: str | None = "6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Get the current database connection
    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if the column exists before attempting to drop it
    columns = [col["name"] for col in inspector.get_columns("podcasts")]
    if "is_generated" in columns:
        op.drop_column("podcasts", "is_generated")


def downgrade() -> None:
    # Add back the is_generated column with its original constraints
    op.add_column(
        "podcasts",
        sa.Column("is_generated", sa.Boolean(), nullable=False, server_default="false"),
    )
