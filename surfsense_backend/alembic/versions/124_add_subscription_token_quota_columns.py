"""124_add_subscription_token_quota_columns

Revision ID: 124
Revises: 123
Create Date: 2026-04-14

Adds subscription and token quota columns to the user table for
cloud-mode LLM billing (Story 3.5).

Columns added:
- monthly_token_limit (Integer, default 100000)
- tokens_used_this_month (Integer, default 0)
- token_reset_date (Date, nullable)
- subscription_status (Enum: free/active/canceled/past_due, default 'free')
- plan_id (String(50), default 'free')
- stripe_customer_id (String(255), nullable, unique)
- stripe_subscription_id (String(255), nullable, unique)

Also creates the 'subscriptionstatus' PostgreSQL enum type.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "124"
down_revision: str | None = "123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Create the enum type so SQLAlchemy's create_type=False works at runtime
subscriptionstatus_enum = sa.Enum(
    "free", "active", "canceled", "past_due",
    name="subscriptionstatus",
)


def upgrade() -> None:
    # Create the PostgreSQL enum type first
    subscriptionstatus_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("user", sa.Column("monthly_token_limit", sa.Integer(), nullable=False, server_default="100000"))
    op.add_column("user", sa.Column("tokens_used_this_month", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user", sa.Column("token_reset_date", sa.Date(), nullable=True))
    op.add_column(
        "user",
        sa.Column(
            "subscription_status",
            subscriptionstatus_enum,
            nullable=False,
            server_default="free",
        ),
    )
    op.add_column("user", sa.Column("plan_id", sa.String(50), nullable=False, server_default="free"))
    op.add_column("user", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("user", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))

    op.create_unique_constraint("uq_user_stripe_customer_id", "user", ["stripe_customer_id"])
    op.create_unique_constraint("uq_user_stripe_subscription_id", "user", ["stripe_subscription_id"])


def downgrade() -> None:
    op.drop_constraint("uq_user_stripe_subscription_id", "user", type_="unique")
    op.drop_constraint("uq_user_stripe_customer_id", "user", type_="unique")
    op.drop_column("user", "stripe_subscription_id")
    op.drop_column("user", "stripe_customer_id")
    op.drop_column("user", "plan_id")
    op.drop_column("user", "subscription_status")
    op.drop_column("user", "token_reset_date")
    op.drop_column("user", "tokens_used_this_month")
    op.drop_column("user", "monthly_token_limit")

    subscriptionstatus_enum.drop(op.get_bind(), checkfirst=True)
