"""106_add_platform_web_search

Revision ID: 106
Revises: 105
Create Date: 2026-03-14

Adds web_search_enabled and web_search_config columns to searchspaces for
per-space control over the platform web search capability.

Also removes legacy SEARXNG_API connector rows — web search is now a platform
service, not a per-user connector.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "106"
down_revision: str | None = "105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "searchspaces",
        sa.Column(
            "web_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "searchspaces",
        sa.Column("web_search_config", JSONB, nullable=True),
    )

    op.execute(
        "DELETE FROM search_source_connectors WHERE connector_type = 'SEARXNG_API'"
    )


def downgrade() -> None:
    op.drop_column("searchspaces", "web_search_config")
    op.drop_column("searchspaces", "web_search_enabled")
