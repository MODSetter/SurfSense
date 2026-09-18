"""encrypt provider api keys

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("provider_connections") as batch:
        batch.drop_column("api_key")
        batch.add_column(
            sa.Column("api_key_ciphertext", sa.LargeBinary(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("provider_connections") as batch:
        batch.drop_column("api_key_ciphertext")
        batch.add_column(sa.Column("api_key", sa.String(), nullable=True))
