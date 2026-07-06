"""Remove AI file sort flag.

Revision ID: 172
Revises: 171
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "172"
down_revision: str | None = "171"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("workspaces", "ai_file_sort_enabled")


def downgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "ai_file_sort_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
