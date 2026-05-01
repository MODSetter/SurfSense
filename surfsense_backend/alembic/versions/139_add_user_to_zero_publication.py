"""add user table to zero_publication with column list

Adds the "user" table to zero_publication with a column-list publication
so that only the 5 fields driving the live usage meters are replicated
through WAL -> zero-cache -> browser IndexedDB:

    id, pages_limit, pages_used,
    premium_tokens_limit, premium_tokens_used

Sensitive columns (hashed_password, email, oauth_account, display_name,
avatar_url, memory_md, refresh_tokens, last_login, etc.) are NOT
included in the publication, so they never enter WAL replication.

Also re-asserts REPLICA IDENTITY DEFAULT on "user" for idempotency
(it is already DEFAULT today since "user" was never in the
TABLES_WITH_FULL_IDENTITY list of migration 117).

IMPORTANT - before AND after running this migration:
  1. Stop zero-cache  (it holds replication locks that will deadlock DDL)
  2. Run:  alembic upgrade head
  3. Delete / reset the zero-cache data volume
  4. Restart zero-cache  (it will do a fresh initial sync)

Revision ID: 139
Revises: 138
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "139"
down_revision: str | None = "138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

# Document column list as left by migration 117. Must match exactly.
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

# Five fields needed by the live usage meters (sidebar Tokens/Pages,
# Buy Tokens content). Keep this list narrow on purpose: anything added
# here flows into WAL and IndexedDB for every connected browser.
USER_COLS = [
    "id",
    "pages_limit",
    "pages_used",
    "premium_tokens_limit",
    "premium_tokens_used",
]


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


def _has_zero_version(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name = '_0_version'"
            ),
            {"tbl": table},
        ).fetchone()
        is not None
    )


def _build_publication_ddl(
    documents_has_zero_ver: bool, user_has_zero_ver: bool
) -> str:
    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
    user_cols = USER_COLS + (['"_0_version"'] if user_has_zero_ver else [])
    doc_col_list = ", ".join(doc_cols)
    user_col_list = ", ".join(user_cols)
    return (
        f"CREATE PUBLICATION {PUBLICATION_NAME} FOR TABLE "
        f"notifications, "
        f"documents ({doc_col_list}), "
        f"folders, "
        f"search_source_connectors, "
        f"new_chat_messages, "
        f"chat_comments, "
        f"chat_session_state, "
        f'"user" ({user_col_list})'
    )


def _build_publication_ddl_without_user(documents_has_zero_ver: bool) -> str:
    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
    doc_col_list = ", ".join(doc_cols)
    return (
        f"CREATE PUBLICATION {PUBLICATION_NAME} FOR TABLE "
        f"notifications, "
        f"documents ({doc_col_list}), "
        f"folders, "
        f"search_source_connectors, "
        f"new_chat_messages, "
        f"chat_comments, "
        f"chat_session_state"
    )


def upgrade() -> None:
    conn = op.get_bind()
    # asyncpg requires LOCK TABLE inside a transaction block. Alembic already
    # opened one via context.begin_transaction(), but the driver still errors
    # unless we use an explicit SAVEPOINT (nested transaction) for this block.
    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(sa.text("SET lock_timeout = '10s'"))

        _terminate_blocked_pids(conn, "user")
        conn.execute(sa.text('LOCK TABLE "user" IN ACCESS EXCLUSIVE MODE'))

        # Idempotent: "user" was never in TABLES_WITH_FULL_IDENTITY of
        # migration 117, so this is already DEFAULT. Re-assert anyway so
        # the column-list publication stays valid (DEFAULT identity only
        # requires the PK to be in the column list).
        conn.execute(sa.text('ALTER TABLE "user" REPLICA IDENTITY DEFAULT'))

        conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}"))

        documents_has_zero_ver = _has_zero_version(conn, "documents")
        user_has_zero_ver = _has_zero_version(conn, "user")

        conn.execute(
            sa.text(_build_publication_ddl(documents_has_zero_ver, user_has_zero_ver))
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}"))
    documents_has_zero_ver = _has_zero_version(conn, "documents")
    conn.execute(sa.text(_build_publication_ddl_without_user(documents_has_zero_ver)))
