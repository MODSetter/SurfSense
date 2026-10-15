"""Keep on each chat thread the sources the user ticked for it.

No row is backfilled: a thread with no scope means every source, which is what
each thread created before this change used.

A plain ALTER TABLE, never batch mode: a batch rebuild drops `chat_threads`,
and with foreign keys on that cascades into every message.

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
    op.execute(sa.text("ALTER TABLE chat_threads ADD COLUMN source_scope JSON"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE chat_threads DROP COLUMN source_scope"))
