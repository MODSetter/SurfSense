"""add license state

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "license_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("certificate", sa.String(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("clock_watermark", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_license_state_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_license_state")),
    )


def downgrade() -> None:
    op.drop_table("license_state")
