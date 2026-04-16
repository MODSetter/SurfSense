"""add premium token quota columns and purchase table

Revision ID: 126
Revises: 125
Create Date: 2026-04-15

Adds premium_tokens_limit, premium_tokens_used, premium_tokens_reserved
to the user table and creates the premium_token_purchases table.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "126"
down_revision: str | None = "125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREMIUM_TOKEN_LIMIT_DEFAULT = os.getenv("PREMIUM_TOKEN_LIMIT", "5000000")


def upgrade() -> None:
    conn = op.get_bind()

    # --- User table: add premium token columns if missing ---
    inspector = sa.inspect(conn)
    user_columns = {c["name"] for c in inspector.get_columns("user")}

    if "premium_tokens_limit" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "premium_tokens_limit",
                sa.BigInteger(),
                nullable=False,
                server_default=PREMIUM_TOKEN_LIMIT_DEFAULT,
            ),
        )
    if "premium_tokens_used" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "premium_tokens_used",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
        )
    if "premium_tokens_reserved" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "premium_tokens_reserved",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
        )

    # --- PremiumTokenPurchase enum + table ---
    enum_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'premiumtokenpurchasestatus'")
    ).fetchone()
    if not enum_exists:
        purchase_status_enum = postgresql.ENUM(
            "PENDING",
            "COMPLETED",
            "FAILED",
            name="premiumtokenpurchasestatus",
            create_type=False,
        )
        purchase_status_enum.create(conn, checkfirst=True)

    if not inspector.has_table("premium_token_purchases"):
        op.create_table(
            "premium_token_purchases",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "stripe_checkout_session_id",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "stripe_payment_intent_id",
                sa.String(length=255),
                nullable=True,
            ),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("tokens_granted", sa.BigInteger(), nullable=False),
            sa.Column("amount_total", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "PENDING",
                    "COMPLETED",
                    "FAILED",
                    name="premiumtokenpurchasestatus",
                    create_type=False,
                ),
                nullable=False,
                server_default=sa.text("'PENDING'::premiumtokenpurchasestatus"),
            ),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "stripe_checkout_session_id",
                name="uq_premium_token_purchases_stripe_checkout_session_id",
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_premium_token_purchases_user_id "
        "ON premium_token_purchases (user_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_premium_token_purchases_stripe_session "
        "ON premium_token_purchases (stripe_checkout_session_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_premium_token_purchases_payment_intent "
        "ON premium_token_purchases (stripe_payment_intent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_premium_token_purchases_status "
        "ON premium_token_purchases (status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_premium_token_purchases_status")
    op.execute("DROP INDEX IF EXISTS ix_premium_token_purchases_payment_intent")
    op.execute("DROP INDEX IF EXISTS ix_premium_token_purchases_stripe_session")
    op.execute("DROP INDEX IF EXISTS ix_premium_token_purchases_user_id")
    op.execute("DROP TABLE IF EXISTS premium_token_purchases")
    postgresql.ENUM(name="premiumtokenpurchasestatus").drop(
        op.get_bind(), checkfirst=True
    )
    op.drop_column("user", "premium_tokens_reserved")
    op.drop_column("user", "premium_tokens_used")
    op.drop_column("user", "premium_tokens_limit")
