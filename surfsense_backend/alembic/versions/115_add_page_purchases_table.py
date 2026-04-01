"""add page purchases table for Stripe-backed page packs

Revision ID: 115
Revises: 114
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "115"
down_revision: str | None = "114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create page_purchases table and supporting enum/indexes."""
    conn = op.get_bind()

    enum_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'pagepurchasestatus'")
    ).fetchone()
    if not enum_exists:
        page_purchase_status_enum = postgresql.ENUM(
            "PENDING",
            "COMPLETED",
            "FAILED",
            name="pagepurchasestatus",
            create_type=False,
        )
        page_purchase_status_enum.create(conn, checkfirst=True)

    table_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'page_purchases'"
        )
    ).fetchone()
    if not table_exists:
        op.create_table(
            "page_purchases",
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
            sa.Column("pages_granted", sa.Integer(), nullable=False),
            sa.Column("amount_total", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "PENDING",
                    "COMPLETED",
                    "FAILED",
                    name="pagepurchasestatus",
                    create_type=False,
                ),
                nullable=False,
                server_default=sa.text("'PENDING'::pagepurchasestatus"),
            ),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "created_at",
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
                name="uq_page_purchases_stripe_checkout_session_id",
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_page_purchases_user_id ON page_purchases (user_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_page_purchases_stripe_checkout_session_id "
        "ON page_purchases (stripe_checkout_session_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_page_purchases_stripe_payment_intent_id "
        "ON page_purchases (stripe_payment_intent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_page_purchases_status ON page_purchases (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_page_purchases_created_at "
        "ON page_purchases (created_at)"
    )


def downgrade() -> None:
    """Drop page_purchases table and enum."""
    op.execute("DROP INDEX IF EXISTS ix_page_purchases_created_at")
    op.execute("DROP INDEX IF EXISTS ix_page_purchases_status")
    op.execute("DROP INDEX IF EXISTS ix_page_purchases_stripe_payment_intent_id")
    op.execute("DROP INDEX IF EXISTS ix_page_purchases_stripe_checkout_session_id")
    op.execute("DROP INDEX IF EXISTS ix_page_purchases_user_id")
    op.execute("DROP TABLE IF EXISTS page_purchases")
    postgresql.ENUM(name="pagepurchasestatus").drop(op.get_bind(), checkfirst=True)
