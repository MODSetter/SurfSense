"""124_add_token_usage_table

Revision ID: 124
Revises: 123
Create Date: 2026-04-14

Adds token_usage table for tracking LLM token consumption per message.
Supports future extension via usage_type for indexing, image gen, etc.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "124"
down_revision: str | None = "123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("token_usage"):
        return

    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_breakdown", JSONB, nullable=True),
        sa.Column("call_details", JSONB, nullable=True),
        sa.Column("usage_type", sa.String(50), nullable=False, server_default="chat"),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("new_chat_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "search_space_id",
            sa.Integer(),
            sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_token_usage_thread_id", "token_usage", ["thread_id"])
    op.create_index("ix_token_usage_message_id", "token_usage", ["message_id"])
    op.create_index("ix_token_usage_search_space_id", "token_usage", ["search_space_id"])
    op.create_index("ix_token_usage_user_id", "token_usage", ["user_id"])
    op.create_index("ix_token_usage_usage_type", "token_usage", ["usage_type"])


def downgrade() -> None:
    op.drop_table("token_usage")
