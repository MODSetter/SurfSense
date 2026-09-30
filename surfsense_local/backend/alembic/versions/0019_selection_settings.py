"""Keep what the user sets for a selected model that no endpoint states.

A JSON column, general to every slot, keyed by the slice that owns each entry.
The first is a server audio model's voices, added by the user when the server
lists none. SQLite adds a nullable column in place, with no table rebuild.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("selected_models", sa.Column("settings", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("selected_models") as table:
        table.drop_column("settings")
