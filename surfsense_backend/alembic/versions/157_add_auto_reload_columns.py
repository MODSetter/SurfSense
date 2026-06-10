"""add auto-reload (off-session Stripe top-up) columns to user

Adds the saved-card + threshold plumbing that powers feature-flagged credit
auto-reload (``AUTO_RELOAD_ENABLED``):

    user.stripe_customer_id              (text, nullable)
    user.auto_reload_enabled             (bool, default false)
    user.auto_reload_threshold_micros    (bigint, nullable)
    user.auto_reload_amount_micros       (bigint, nullable)
    user.auto_reload_payment_method_id   (text, nullable)
    user.auto_reload_failed_at           (timestamptz, nullable)

None of these columns are part of the Zero publication (``USER_COLS`` is
``["id", "credit_micros_balance"]``), so this migration does NOT touch the
publication and is safe to run without the zero-cache stop/reset dance that
migration 156 required.

The ``credit_purchases.source`` column (``checkout`` | ``auto_reload``) was
already added in migration 156, so it is not repeated here.

Revision ID: 157
Revises: 156
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "157"
down_revision: str | None = "156"
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


_COLUMNS: list[tuple[str, sa.Column]] = [
    ("stripe_customer_id", sa.Column("stripe_customer_id", sa.String(), nullable=True)),
    (
        "auto_reload_enabled",
        sa.Column(
            "auto_reload_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    ),
    (
        "auto_reload_threshold_micros",
        sa.Column("auto_reload_threshold_micros", sa.BigInteger(), nullable=True),
    ),
    (
        "auto_reload_amount_micros",
        sa.Column("auto_reload_amount_micros", sa.BigInteger(), nullable=True),
    ),
    (
        "auto_reload_payment_method_id",
        sa.Column("auto_reload_payment_method_id", sa.String(), nullable=True),
    ),
    (
        "auto_reload_failed_at",
        sa.Column("auto_reload_failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
