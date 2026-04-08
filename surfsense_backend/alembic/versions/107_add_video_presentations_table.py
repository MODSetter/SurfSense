"""Add video_presentations table and video_presentation_status enum

Revision ID: 107
Revises: 106
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB

from alembic import op

revision: str = "107"
down_revision: str | None = "106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

video_presentation_status_enum = ENUM(
    "pending",
    "generating",
    "ready",
    "failed",
    name="video_presentation_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE video_presentation_status AS ENUM ('pending', 'generating', 'ready', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'video_presentations'"
        )
    )
    if not result.fetchone():
        op.create_table(
            "video_presentations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("slides", JSONB(), nullable=True),
            sa.Column("scene_codes", JSONB(), nullable=True),
            sa.Column(
                "status",
                video_presentation_status_enum,
                server_default="ready",
                nullable=False,
            ),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("thread_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["search_space_id"],
                ["searchspaces.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["thread_id"],
                ["new_chat_threads.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index(
        "ix_video_presentations_status",
        "video_presentations",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_video_presentations_thread_id",
        "video_presentations",
        ["thread_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_video_presentations_created_at",
        "video_presentations",
        ["created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_video_presentations_created_at", table_name="video_presentations")
    op.drop_index("ix_video_presentations_thread_id", table_name="video_presentations")
    op.drop_index("ix_video_presentations_status", table_name="video_presentations")
    op.drop_table("video_presentations")
    op.execute("DROP TYPE IF EXISTS video_presentation_status")
