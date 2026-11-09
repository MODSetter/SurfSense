"""Keep the SearXNG server Add from the web searches with, when the user names one.

No row, or no URL, means SurfSense's own server.

Revision ID: 0034
Revises: 0033
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "web_search_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("searxng_url", sa.String(), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_web_search_settings_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_web_search_settings")),
    )


def downgrade() -> None:
    op.drop_table("web_search_settings")
