"""rename premium token columns to credit micros and add cost_micros to token_usage

Migrates the premium quota system from a flat token counter to a USD-cost
based credit system, where 1 credit = 1 micro-USD ($0.000001).

Column renames (1:1 numerical mapping — the prior $1 per 1M tokens Stripe
price means every existing value is already correct in the new unit, no
data transformation needed):

    user.premium_tokens_limit       -> premium_credit_micros_limit
    user.premium_tokens_used        -> premium_credit_micros_used
    user.premium_tokens_reserved    -> premium_credit_micros_reserved

    premium_token_purchases.tokens_granted -> credit_micros_granted

New column for cost auditing per turn:

    token_usage.cost_micros (BigInteger NOT NULL DEFAULT 0)

The "user" table is in zero_publication's column list (added in 139), so
this migration must drop and recreate the publication with the renamed
column names, otherwise zero-cache will replicate stale column names and
the FE Zero schema will fail to bind.

IMPORTANT - before AND after running this migration:
  1. Stop zero-cache  (it holds replication locks that will deadlock DDL)
  2. Run:  alembic upgrade head
  3. Delete / reset the zero-cache data volume
  4. Restart zero-cache  (it will do a fresh initial sync)

Skipping the zero-cache stop will deadlock at the ACCESS EXCLUSIVE LOCK on
"user". Skipping the data-volume reset will leave IndexedDB clients seeing
column-not-found errors from a stale catalog snapshot.

Revision ID: 140
Revises: 139
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "140"
down_revision: str | None = "139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"

# Replicates 139's document column list verbatim — must stay in sync.
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

# Same five live-meter fields as 139, with the renamed column names.
USER_COLS = [
    "id",
    "pages_limit",
    "pages_used",
    "premium_credit_micros_limit",
    "premium_credit_micros_used",
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


def _column_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name = :col"
            ),
            {"tbl": table, "col": column},
        ).fetchone()
        is not None
    )


def _build_publication_ddl(
    user_cols: list[str],
    *,
    documents_has_zero_ver: bool,
    user_has_zero_ver: bool,
) -> str:
    doc_cols = DOCUMENT_COLS + (['"_0_version"'] if documents_has_zero_ver else [])
    user_col_list_with_meta = user_cols + (
        ['"_0_version"'] if user_has_zero_ver else []
    )
    doc_col_list = ", ".join(doc_cols)
    user_col_list = ", ".join(user_col_list_with_meta)
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


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Add cost_micros to token_usage. Idempotent guard so re-runs in
    #    dev environments are safe.
    # ------------------------------------------------------------------
    if not _column_exists(conn, "token_usage", "cost_micros"):
        op.add_column(
            "token_usage",
            sa.Column(
                "cost_micros",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
        )

    # ------------------------------------------------------------------
    # 2. Rename premium_token_purchases.tokens_granted -> credit_micros_granted.
    # ------------------------------------------------------------------
    if _column_exists(
        conn, "premium_token_purchases", "tokens_granted"
    ) and not _column_exists(conn, "premium_token_purchases", "credit_micros_granted"):
        op.alter_column(
            "premium_token_purchases",
            "tokens_granted",
            new_column_name="credit_micros_granted",
        )

    # ------------------------------------------------------------------
    # 3. Rename user.premium_tokens_* -> premium_credit_micros_*.
    #
    # We must drop the publication first (it references the old column
    # names) and re-acquire the lock for DDL. asyncpg requires LOCK TABLE
    # in a transaction block; alembic's outer transaction already holds
    # one, but a SAVEPOINT keeps the LOCK + DDL atomic.
    # ------------------------------------------------------------------
    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(sa.text("SET lock_timeout = '10s'"))

        _terminate_blocked_pids(conn, "user")
        conn.execute(sa.text('LOCK TABLE "user" IN ACCESS EXCLUSIVE MODE'))

        # Re-assert REPLICA IDENTITY DEFAULT for safety; column-list
        # publications require at least the PK to be in the column list,
        # which is true for both the old and new shape.
        conn.execute(sa.text('ALTER TABLE "user" REPLICA IDENTITY DEFAULT'))

        # Drop the publication BEFORE renaming columns, otherwise Postgres
        # rejects the rename: "cannot drop column ... referenced by
        # publication".
        conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}"))

        for old, new in (
            ("premium_tokens_limit", "premium_credit_micros_limit"),
            ("premium_tokens_used", "premium_credit_micros_used"),
            ("premium_tokens_reserved", "premium_credit_micros_reserved"),
        ):
            if _column_exists(conn, "user", old) and not _column_exists(
                conn, "user", new
            ):
                op.alter_column("user", old, new_column_name=new)

        # Update the server_default on the renamed limit column so newly
        # inserted users get $5 of credit (== 5_000_000 micros) by
        # default. Existing rows are unaffected.
        op.alter_column(
            "user",
            "premium_credit_micros_limit",
            server_default="5000000",
        )

        # Recreate the publication with the new column names.
        documents_has_zero_ver = _has_zero_version(conn, "documents")
        user_has_zero_ver = _has_zero_version(conn, "user")
        conn.execute(
            sa.text(
                _build_publication_ddl(
                    USER_COLS,
                    documents_has_zero_ver=documents_has_zero_ver,
                    user_has_zero_ver=user_has_zero_ver,
                )
            )
        )


def downgrade() -> None:
    """Revert the rename and drop ``cost_micros``.

    Mirrors ``upgrade``: drop the publication, rename columns back, drop
    the new column, recreate the publication with the old column list.
    Same zero-cache stop/reset runbook applies in reverse.
    """
    conn = op.get_bind()

    tx = conn.begin_nested() if conn.in_transaction() else conn.begin()
    with tx:
        conn.execute(sa.text("SET lock_timeout = '10s'"))

        _terminate_blocked_pids(conn, "user")
        conn.execute(sa.text('LOCK TABLE "user" IN ACCESS EXCLUSIVE MODE'))

        conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {PUBLICATION_NAME}"))

        for new, old in (
            ("premium_credit_micros_limit", "premium_tokens_limit"),
            ("premium_credit_micros_used", "premium_tokens_used"),
            ("premium_credit_micros_reserved", "premium_tokens_reserved"),
        ):
            if _column_exists(conn, "user", new) and not _column_exists(
                conn, "user", old
            ):
                op.alter_column("user", new, new_column_name=old)

        op.alter_column(
            "user",
            "premium_tokens_limit",
            server_default="5000000",
        )

        legacy_user_cols = [
            "id",
            "pages_limit",
            "pages_used",
            "premium_tokens_limit",
            "premium_tokens_used",
        ]
        documents_has_zero_ver = _has_zero_version(conn, "documents")
        user_has_zero_ver = _has_zero_version(conn, "user")
        conn.execute(
            sa.text(
                _build_publication_ddl(
                    legacy_user_cols,
                    documents_has_zero_ver=documents_has_zero_ver,
                    user_has_zero_ver=user_has_zero_ver,
                )
            )
        )

    if _column_exists(
        conn, "premium_token_purchases", "credit_micros_granted"
    ) and not _column_exists(conn, "premium_token_purchases", "tokens_granted"):
        op.alter_column(
            "premium_token_purchases",
            "credit_micros_granted",
            new_column_name="tokens_granted",
        )

    if _column_exists(conn, "token_usage", "cost_micros"):
        op.drop_column("token_usage", "cost_micros")
