"""Remember the hosted identity of an imported chat thread.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_threads") as batch:
        batch.add_column(sa.Column("cloud_id", sa.Integer(), nullable=True))
        batch.create_unique_constraint(op.f("uq_chat_threads_cloud_id"), ["cloud_id"])


def downgrade() -> None:
    with op.batch_alter_table("chat_threads") as batch:
        batch.drop_constraint(op.f("uq_chat_threads_cloud_id"), type_="unique")
        batch.drop_column("cloud_id")
