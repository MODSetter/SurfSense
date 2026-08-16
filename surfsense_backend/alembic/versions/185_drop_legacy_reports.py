"""Drop the legacy reports table and seeded resume prompt.

Revision ID: 185
Revises: 184
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "185"
down_revision: str | None = "184"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM prompts WHERE default_prompt_slug = 'build-resume'")
    op.drop_table("reports")


def downgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "content_type",
            sa.String(length=20),
            nullable=False,
            server_default="markdown",
        ),
        sa.Column(
            "report_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("report_style", sa.String(length=100), nullable=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_group_id", sa.Integer(), nullable=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    # Migration 170 renamed the column but intentionally left this legacy
    # index name unchanged; recreate the schema as it existed at revision 184.
    op.create_index("ix_reports_search_space_id", "reports", ["workspace_id"])
    op.create_index("ix_reports_report_group_id", "reports", ["report_group_id"])
    op.create_index("ix_reports_thread_id", "reports", ["thread_id"])
    op.create_index("ix_reports_created_at", "reports", ["created_at"])
