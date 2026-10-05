"""Remember where each chat thread's trimmed history starts.

Nothing is backfilled: a thread with no start sends its whole history until it
first outgrows the window.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE chat_threads ADD COLUMN history_start_message_id INTEGER")
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE chat_threads DROP COLUMN history_start_message_id"))
