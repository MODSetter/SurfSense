"""record what is known about the selected model

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("selected_models") as batch:
        batch.add_column(sa.Column("params_b", sa.Float(), nullable=True))
        batch.add_column(sa.Column("vendor", sa.String(), nullable=True))
        batch.add_column(
            sa.Column(
                "line",
                sa.Enum(
                    "flagship",
                    "small",
                    name="line",
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("selected_models") as batch:
        batch.drop_column("line")
        batch.drop_column("vendor")
        batch.drop_column("params_b")
