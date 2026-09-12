"""add workspace cloud_id

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("cloud_id", sa.Integer(), nullable=True))
        batch.create_unique_constraint(op.f("uq_workspaces_cloud_id"), ["cloud_id"])


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_constraint(op.f("uq_workspaces_cloud_id"), type_="unique")
        batch.drop_column("cloud_id")
