"""Remember the hosted identity of an imported chat thread.

Both columns use plain ALTER TABLE: rebuilding either parent table with foreign
keys enabled would cascade-delete its child rows.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
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
              SELECT 1
              FROM chat_threads
              JOIN chat_messages
                ON chat_messages.chat_thread_id = chat_threads.id
              WHERE chat_threads.workspace_id = workspaces.id
                AND chat_messages.role IN ('user', 'assistant')
                AND json_type(
                    chat_messages.content, '$.citations'
                ) IS NOT NULL
                AND chat_messages.completed_at = chat_messages.created_at
          )
        """
    )


def downgrade() -> None:
    op.drop_column("workspaces", "has_unkeyed_imported_threads")
    op.drop_index("chat_threads_cloud_id", table_name="chat_threads")
    op.drop_column("chat_threads", "cloud_id")
