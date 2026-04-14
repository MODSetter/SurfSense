"""127_add_subscription_requests_table

Revision ID: 127
Revises: 126
Create Date: 2026-04-15

Adds the subscription_requests table for admin-approval flow when Stripe
is not configured. Users submit a subscription request; superusers can
approve/reject it from the admin panel.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "127"
down_revision: str | None = "126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Drop any pre-existing enum (e.g. uppercase version from old create_all())
    conn.execute(sa.text("DROP TYPE IF EXISTS subscriptionrequeststatus"))
    conn.execute(
        sa.text(
            "CREATE TYPE subscriptionrequeststatus AS ENUM ('pending', 'approved', 'rejected')"
        )
    )
    conn.execute(
        sa.text(
            """
            CREATE TABLE subscription_requests (
                id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID         NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                plan_id     VARCHAR(50)  NOT NULL,
                status      subscriptionrequeststatus NOT NULL DEFAULT 'pending',
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                approved_at TIMESTAMPTZ,
                approved_by UUID         REFERENCES "user"(id)
            )
            """
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX ix_subscription_requests_user_id ON subscription_requests (user_id)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS subscription_requests"))
    conn.execute(sa.text("DROP TYPE IF EXISTS subscriptionrequeststatus"))
