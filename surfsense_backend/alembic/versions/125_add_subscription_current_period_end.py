"""125_add_subscription_current_period_end

Revision ID: 125
Revises: 124
Create Date: 2026-04-15

Adds subscription_current_period_end column to the user table for
tracking when the current billing period ends (Story 5.3).

Column added:
- subscription_current_period_end (TIMESTAMP with timezone, nullable)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "125"
down_revision: str | None = "124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("subscription_current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "subscription_current_period_end")
