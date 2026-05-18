"""create zero_publication for zero-cache replication

Restricts zero-cache replication to only the tables the frontend
queries via Zero, instead of replicating all tables in public schema.

See: https://zero.rocicorp.dev/docs/zero-cache-config#app-publications

NOTE for future migration authors: this is the ONLY migration allowed
to use bare ``CREATE PUBLICATION``. All subsequent mutations of
``zero_publication`` MUST use the ``COMMENT ON PUBLICATION`` bookend
pattern wrapping an ``ALTER PUBLICATION ... SET TABLE`` -- copy the
``upgrade()`` function from migration
``143_force_zero_publication_resync.py`` as your starting template.
Raw ``DROP``/``CREATE PUBLICATION`` in new migrations would
re-introduce bug #1355 (zero-cache stuck on a stale replica snapshot
because Zero >= 1.0's change-streamer never sees the schema-change
event).

Revision ID: 116
Revises: 115
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "116"
down_revision: str | None = "115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

TABLES = [
    "notifications",
    "documents",
    "folders",
    "search_source_connectors",
    "new_chat_messages",
    "chat_comments",
    "chat_session_state",
]


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_publication WHERE pubname = :name"),
        {"name": PUBLICATION_NAME},
    ).fetchone()
    if not exists:
        table_list = ", ".join(TABLES)
        conn.execute(
            sa.text(f"CREATE PUBLICATION {PUBLICATION_NAME} FOR TABLE {table_list}")
        )


def downgrade() -> None:
    op.execute(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}")
