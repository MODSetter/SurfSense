"""optimize zero_publication with column lists

Recreates the zero_publication using column lists for the documents
table so that large text columns (content, source_markdown,
blocknote_document, etc.) are excluded from WAL replication.
This prevents RangeError: Invalid string length in zero-cache's
change-streamer when documents have very large content.

Also resets REPLICA IDENTITY to DEFAULT on tables that had it set
to FULL for the old Electric SQL setup (migration 66/75/76).
With DEFAULT (primary-key) identity, column-list publications
only need to include the PK — not every column.

IMPORTANT — before AND after running this migration:
  1. Stop zero-cache  (it holds replication locks that will deadlock DDL)
  2. Run:  alembic upgrade head
  3. Delete / reset the zero-cache data volume
  4. Restart zero-cache  (it will do a fresh initial sync)

Revision ID: 117
Revises: 116
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "117"
down_revision: str | None = "116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

TABLES_WITH_FULL_IDENTITY = [
    "documents",
    "notifications",
    "search_source_connectors",
    "new_chat_messages",
    "chat_comments",
    "chat_session_state",
]

DOCUMENT_COLS = [
    "id",
    "title",
    "document_type",
    "search_space_id",
    "folder_id",
    "created_by_id",
    "status",
    "created_at",
    "updated_at",
]

PUBLICATION_DDL_FULL = f"""\
CREATE PUBLICATION {PUBLICATION_NAME} FOR TABLE
  notifications, documents, folders,
  search_source_connectors, new_chat_messages,
  chat_comments, chat_session_state
"""


def _terminate_blocked_pids(conn, table: str) -> None:
    """Kill backends whose locks on *table* would block our AccessExclusiveLock."""
    conn.execute(
        sa.text(
            "SELECT pg_terminate_backend(l.pid) "
            "FROM pg_locks l "
            "JOIN pg_class c ON c.oid = l.relation "
            "WHERE c.relname = :tbl "
            "  AND l.pid != pg_backend_pid()"
        ),
        {"tbl": table},
    )


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("SET lock_timeout = '10s'"))

    for tbl in sorted(TABLES_WITH_FULL_IDENTITY):
        _terminate_blocked_pids(conn, tbl)
        conn.execute(sa.text(f'LOCK TABLE "{tbl}" IN ACCESS EXCLUSIVE MODE'))

    for tbl in TABLES_WITH_FULL_IDENTITY:
        conn.execute(sa.text(f'ALTER TABLE "{tbl}" REPLICA IDENTITY DEFAULT'))

    conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}"))

    has_zero_ver = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'documents' AND column_name = '_0_version'"
        )
    ).fetchone()

    cols = DOCUMENT_COLS + (['"_0_version"'] if has_zero_ver else [])
    col_list = ", ".join(cols)

    conn.execute(
        sa.text(
            f"CREATE PUBLICATION {PUBLICATION_NAME} FOR TABLE "
            f"notifications, "
            f"documents ({col_list}), "
            f"folders, "
            f"search_source_connectors, "
            f"new_chat_messages, "
            f"chat_comments, "
            f"chat_session_state"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}"))
    conn.execute(sa.text(PUBLICATION_DDL_FULL))
    for tbl in TABLES_WITH_FULL_IDENTITY:
        conn.execute(sa.text(f'ALTER TABLE "{tbl}" REPLICA IDENTITY FULL'))
