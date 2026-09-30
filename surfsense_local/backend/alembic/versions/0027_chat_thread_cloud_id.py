"""Remember the hosted identity of an imported chat thread.

Both columns use plain ALTER TABLE: rebuilding either parent table with foreign
keys enabled would cascade-delete its child rows.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_threads", sa.Column("cloud_id", sa.Integer(), nullable=True))
    op.create_index("chat_threads_cloud_id", "chat_threads", ["cloud_id"], unique=True)
    op.add_column(
        "workspaces",
        sa.Column(
            "has_unkeyed_imported_threads",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        """
        UPDATE workspaces
        SET has_unkeyed_imported_threads = 1
        WHERE cloud_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM chat_threads
              WHERE chat_threads.workspace_id = workspaces.id
          )
        """
    )


def downgrade() -> None:
    op.drop_column("workspaces", "has_unkeyed_imported_threads")
    op.drop_index("chat_threads_cloud_id", table_name="chat_threads")
    op.drop_column("chat_threads", "cloud_id")
