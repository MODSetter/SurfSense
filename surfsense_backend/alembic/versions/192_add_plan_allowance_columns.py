"""add plan + allowance columns to user (subscription groundwork)

Splits the wallet into two buckets so a recurring monthly grant can expire
without touching credit a user paid cash for:

    user.credit_micros_allowance   (bigint, default 0)  -- plan grant, resets
    user.allowance_period_end      (timestamptz, null)  -- end of the period
    user.plan                      (text, default 'free')

``credit_micros_balance`` keeps its existing meaning — permanent money from
purchases, incentive rewards, and auto-reload — and is deliberately left
untouched here, so purchased credit needs no data migration at all.

This migration is inert on its own. ``credit_micros_allowance`` defaults to 0
for every existing row, and ``wallet_credit.drain`` spends the allowance before
the balance, so with a zero allowance every debit behaves exactly as it did
before. Granting an allowance is a separate change.

None of these columns are in the Zero publication (``USER_COLS`` is
``["id", "credit_micros_balance"]``), so this does not touch the publication
and needs no zero-cache stop/reset.

Revision ID: 192
Revises: 191
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "192"
down_revision: str | None = "191"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name = :col "
                "AND table_schema = current_schema()"
            ),
            {"tbl": table, "col": column},
        ).fetchone()
        is not None
    )


_COLUMNS: list[tuple[str, sa.Column]] = [
    (
        "credit_micros_allowance",
        sa.Column(
            "credit_micros_allowance",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    ),
    (
        "allowance_period_end",
        sa.Column("allowance_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
    ),
    (
        "plan",
        sa.Column(
            "plan",
            sa.String(),
            nullable=False,
            server_default=sa.text("'free'"),
        ),
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, column in _COLUMNS:
        if not _column_exists(conn, "user", name):
            op.add_column("user", column)


def downgrade() -> None:
    conn = op.get_bind()
    for name, _ in reversed(_COLUMNS):
        if _column_exists(conn, "user", name):
            op.drop_column("user", name)
