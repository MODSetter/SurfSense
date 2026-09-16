"""allow cancelling a background document job

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _status(*values: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name="documentstatus",
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.alter_column(
            "status",
            existing_type=_status("pending", "processing", "ready", "failed"),
            type_=_status(
                "pending", "processing", "ready", "failed", "cancelled"
            ),
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE documents SET status = 'failed' WHERE status = 'cancelled'")
    )
    with op.batch_alter_table("documents") as batch:
        batch.alter_column(
            "status",
            existing_type=_status(
                "pending", "processing", "ready", "failed", "cancelled"
            ),
            type_=_status("pending", "processing", "ready", "failed"),
            existing_nullable=False,
        )
