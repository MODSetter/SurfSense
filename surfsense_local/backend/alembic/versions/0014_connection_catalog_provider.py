"""Record which manifest provider a connection reaches.

Existing connections become `custom`: their provider was never recorded, and
reading it back from the URL is the guess the design refuses, so they keep
today's behaviour until the user picks one.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("provider_connections") as batch:
        batch.add_column(
            sa.Column(
                "catalog_provider",
                sa.String(),
                nullable=False,
                server_default="custom",
            )
        )


def downgrade() -> None:
    # In place, not through a batch rebuild: dropping the old table would fire
    # selected_models' ON DELETE CASCADE and take every remote selection with it.
    op.execute(sa.text("ALTER TABLE provider_connections DROP COLUMN catalog_provider"))
