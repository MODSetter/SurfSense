"""unify page limits and premium credits into a single credit_micros_balance wallet

Collapses the two separate economies (ETL ``pages_limit``/``pages_used`` and
premium ``premium_credit_micros_limit``/``premium_credit_micros_used``) into one
USD-micro wallet column ``user.credit_micros_balance`` that decreases on use and
increases on purchase / grant. ``premium_credit_micros_reserved`` is kept (renamed
to ``credit_micros_reserved``) for in-flight reservation holds.

Backfill (per existing user row):

    balance = GREATEST(0, premium_credit_micros_limit - premium_credit_micros_used)
            + (CASE WHEN pages_limit < 100000000
                    THEN GREATEST(0, pages_limit - pages_used) * 1000
                    ELSE 0 END)

The ``pages_limit < 100000000`` guard skips the OSS "unlimited" default
(``PAGES_LIMIT=999999999``) so self-hosters don't get a ~$1M credit grant.
1 page == 1000 micros == $0.001 (matches the prior $1 / 1000 pages price).

Table / type renames:

    premium_token_purchases          -> credit_purchases
    premiumtokenpurchasestatus (enum)-> creditpurchasestatus
    user_incentive_tasks.pages_awarded -> credit_micros_awarded (backfilled * 1000)

The "user" table is in zero_publication's column list, so this migration updates
the publication via ``apply_publication`` (canonical reconcile, per migration 155)
BEFORE dropping the old columns it referenced.

IMPORTANT - before AND after running this migration (same as migration 140):
  1. Stop zero-cache  (it holds replication locks that will deadlock DDL)
  2. Run:  alembic upgrade head
  3. Delete / reset the zero-cache data volume
  4. Restart zero-cache  (it will do a fresh initial sync)

Revision ID: 156
Revises: 155
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.zero_publication import apply_publication

revision: str = "156"
down_revision: str | None = "155"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = :tbl AND table_schema = current_schema()"
            ),
            {"tbl": table},
        ).fetchone()
        is not None
    )


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

    # ------------------------------------------------------------------
    # 1. Add credit_micros_balance + backfill from both legacy economies.
    # ------------------------------------------------------------------
    if not _column_exists(conn, "user", "credit_micros_balance"):
        op.add_column(
            "user",
            sa.Column(
                "credit_micros_balance",
                sa.BigInteger(),
                nullable=False,
                server_default="5000000",
            ),
        )

        # Backfill only when the legacy source columns are present (fresh DBs
        # created from current models won't have them).
        if _column_exists(
            conn, "user", "premium_credit_micros_limit"
        ) and _column_exists(conn, "user", "pages_limit"):
            conn.execute(
                sa.text(
                    'UPDATE "user" SET credit_micros_balance = '
                    "GREATEST(0, premium_credit_micros_limit - premium_credit_micros_used) "
                    "+ (CASE WHEN pages_limit < 100000000 "
                    "        THEN GREATEST(0, pages_limit - pages_used) * 1000 "
                    "        ELSE 0 END)"
                )
            )

    # ------------------------------------------------------------------
    # 2. Rename premium_credit_micros_reserved -> credit_micros_reserved.
    # ------------------------------------------------------------------
    if _column_exists(
        conn, "user", "premium_credit_micros_reserved"
    ) and not _column_exists(conn, "user", "credit_micros_reserved"):
        op.alter_column(
            "user",
            "premium_credit_micros_reserved",
            new_column_name="credit_micros_reserved",
        )

    # ------------------------------------------------------------------
    # 3. Reconcile the Zero publication to the new column list
    #    (id, credit_micros_balance) BEFORE dropping the columns it used
    #    to reference, otherwise Postgres rejects the column drops with
    #    "cannot drop column ... referenced by publication".
    # ------------------------------------------------------------------
    conn.execute(sa.text("SET lock_timeout = '10s'"))
    _terminate_blocked_pids(conn, "user")
    apply_publication(conn)

    # ------------------------------------------------------------------
    # 4. Drop the legacy quota columns now that nothing references them.
    # ------------------------------------------------------------------
    for col in (
        "premium_credit_micros_limit",
        "premium_credit_micros_used",
        "pages_limit",
        "pages_used",
    ):
        if _column_exists(conn, "user", col):
            op.drop_column("user", col)

    # ------------------------------------------------------------------
    # 5. Rename premium_token_purchases -> credit_purchases and its enum.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'premiumtokenpurchasestatus')
               AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'creditpurchasestatus')
            THEN
                ALTER TYPE premiumtokenpurchasestatus RENAME TO creditpurchasestatus;
            END IF;
        END
        $$;
        """
    )

    if _table_exists(conn, "premium_token_purchases") and not _table_exists(
        conn, "credit_purchases"
    ):
        op.rename_table("premium_token_purchases", "credit_purchases")

    # ``source`` distinguishes user checkout from auto-reload top-ups.
    if _table_exists(conn, "credit_purchases") and not _column_exists(
        conn, "credit_purchases", "source"
    ):
        op.add_column(
            "credit_purchases",
            sa.Column(
                "source",
                sa.String(length=20),
                nullable=False,
                server_default="checkout",
            ),
        )

    # ------------------------------------------------------------------
    # 6. Rename user_incentive_tasks.pages_awarded -> credit_micros_awarded
    #    and convert page counts to micros (1 page == 1000 micros).
    # ------------------------------------------------------------------
    if _column_exists(
        conn, "user_incentive_tasks", "pages_awarded"
    ) and not _column_exists(conn, "user_incentive_tasks", "credit_micros_awarded"):
        op.alter_column(
            "user_incentive_tasks",
            "pages_awarded",
            new_column_name="credit_micros_awarded",
            type_=sa.BigInteger(),
        )
        conn.execute(
            sa.text(
                "UPDATE user_incentive_tasks "
                "SET credit_micros_awarded = credit_micros_awarded * 1000"
            )
        )


def downgrade() -> None:
    """No-op. This is a one-way data-model unification; the legacy split
    columns cannot be faithfully reconstructed from a single balance."""
