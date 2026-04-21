"""127_add_report_content_type

Revision ID: 127
Revises: 126
Create Date: 2026-04-15

Adds content_type column to reports table to distinguish between
Markdown reports and Typst-based resumes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "127"
down_revision: str | None = "126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = [c["name"] for c in sa.inspect(conn).get_columns("reports")]
    if "content_type" in columns:
        return
    op.add_column(
        "reports",
        sa.Column(
            "content_type",
            sa.String(20),
            nullable=False,
            server_default="markdown",
        ),
    )


def downgrade() -> None:
    op.drop_column("reports", "content_type")
