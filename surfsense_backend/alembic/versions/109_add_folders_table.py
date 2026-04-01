"""Add folders table and folder_id to documents

Revision ID: 109
Revises: 108

Creates the folders table for nested folder organization (max 8 levels),
adds folder_id FK to documents, and creates an expression-based unique
index to correctly handle NULL parent_id at root level.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "109"
down_revision: str | None = "108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "folders" not in existing_tables:
        op.create_table(
            "folders",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(255), nullable=False, index=True),
            sa.Column("position", sa.String(50), nullable=False, index=True),
            sa.Column(
                "parent_id",
                sa.Integer(),
                sa.ForeignKey("folders.id", ondelete="CASCADE"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "search_space_id",
                sa.Integer(),
                sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "created_by_id",
                sa.Uuid(),
                sa.ForeignKey("user.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # Expression-based unique index: COALESCE(parent_id, 0) handles NULL correctly.
    # PostgreSQL treats NULL != NULL in regular unique constraints, so a standard
    # UniqueConstraint(search_space_id, parent_id, name) would allow duplicate
    # folder names at the root level.
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("folders")]
    if "uq_folder_space_parent_name" not in existing_indexes:
        op.execute(
            """
            CREATE UNIQUE INDEX uq_folder_space_parent_name
            ON folders (search_space_id, COALESCE(parent_id, 0), name);
            """
        )

    existing_columns = [col["name"] for col in inspector.get_columns("documents")]
    if "folder_id" not in existing_columns:
        op.add_column(
            "documents",
            sa.Column(
                "folder_id",
                sa.Integer(),
                sa.ForeignKey("folders.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("documents", "folder_id")
    op.execute("DROP INDEX IF EXISTS uq_folder_space_parent_name;")
    op.drop_table("folders")
