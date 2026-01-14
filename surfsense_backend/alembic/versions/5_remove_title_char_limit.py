"""Remove char limit on title columns

Revision ID: 5
Revises: 4

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5"
down_revision: str | None = "4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
        ),
        {"table_name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    # Alter Chat table (may not exist on fresh databases, removed in migration 49)
    if table_exists("chats"):
        op.alter_column(
            "chats",
            "title",
            existing_type=sa.String(200),
            type_=sa.String(),
            existing_nullable=False,
        )

    # Alter Document table
    if table_exists("documents"):
        op.alter_column(
            "documents",
            "title",
            existing_type=sa.String(200),
            type_=sa.String(),
            existing_nullable=False,
        )

    # Alter Podcast table
    if table_exists("podcasts"):
        op.alter_column(
            "podcasts",
            "title",
            existing_type=sa.String(200),
            type_=sa.String(),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Revert Chat table
    if table_exists("chats"):
        op.alter_column(
            "chats",
            "title",
            existing_type=sa.String(),
            type_=sa.String(200),
            existing_nullable=False,
        )

    # Revert Document table
    if table_exists("documents"):
        op.alter_column(
            "documents",
            "title",
            existing_type=sa.String(),
            type_=sa.String(200),
            existing_nullable=False,
        )

    # Revert Podcast table
    if table_exists("podcasts"):
        op.alter_column(
            "podcasts",
            "title",
            existing_type=sa.String(),
            type_=sa.String(200),
            existing_nullable=False,
        )
