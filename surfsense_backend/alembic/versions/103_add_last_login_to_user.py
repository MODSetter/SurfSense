"""103_add_last_login_to_user

Revision ID: 103
Revises: 102
Create Date: 2026-03-08

Adds last_login timestamp column to the user table so we can track
when each user last authenticated.  The column is nullable — existing
rows will have NULL until the user's next login.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "103"
down_revision: str | None = "102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_columns = [col["name"] for col in sa.inspect(conn).get_columns("user")]

    if "last_login" not in existing_columns:
        op.add_column(
            "user",
            sa.Column("last_login", sa.TIMESTAMP(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("user", "last_login")
