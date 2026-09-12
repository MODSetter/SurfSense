"""add onboarding completion

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "onboarding_completion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_onboarding_completion_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboarding_completion")),
    )


def downgrade() -> None:
    op.drop_table("onboarding_completion")
