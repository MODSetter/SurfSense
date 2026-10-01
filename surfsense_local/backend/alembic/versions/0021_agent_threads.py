"""Let a chat thread be the agent's: it keeps the opencode session that holds its turns.

Null for every thread before this and for every thread the chat answers. An
agent thread's turns live in opencode's own database, so this is all it adds.
SQLite adds a nullable column in place, with no table rebuild.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_threads", sa.Column("opencode_session_id", sa.String(), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("chat_threads") as table:
        table.drop_column("opencode_session_id")
