"""130_add_agent_action_log

Revision ID: 130
Revises: 129
Create Date: 2026-04-28

Tier 5.2 in the OpenCode-port plan. Adds the append-only ``agent_action_log``
table that :class:`ActionLogMiddleware` writes to after every tool call.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "130"
down_revision: str | None = "129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_action_log",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "search_space_id",
            sa.Integer(),
            sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("turn_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("message_id", sa.String(length=128), nullable=True, index=True),
        sa.Column("tool_name", sa.String(length=255), nullable=False, index=True),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_id", sa.String(length=255), nullable=True),
        sa.Column(
            "reversible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "reverse_descriptor",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "reverse_of",
            sa.Integer(),
            sa.ForeignKey("agent_action_log.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            index=True,
        ),
    )
    op.create_index(
        "ix_agent_action_log_thread_created",
        "agent_action_log",
        ["thread_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_action_log_thread_created", table_name="agent_action_log")
    op.drop_table("agent_action_log")
