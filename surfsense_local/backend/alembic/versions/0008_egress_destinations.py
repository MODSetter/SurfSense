"""add egress destinations

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "egress_destinations",
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_call_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("destination", name=op.f("pk_egress_destinations")),
    )


def downgrade() -> None:
    op.drop_table("egress_destinations")
