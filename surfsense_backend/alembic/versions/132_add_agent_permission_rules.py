"""132_add_agent_permission_rules

Revision ID: 132
Revises: 131
Create Date: 2026-04-28

Adds the persistent ``agent_permission_rules`` table consumed by
:class:`PermissionMiddleware` at agent build time. Rules can be scoped
at search-space (``user_id`` / ``thread_id`` NULL), user-wide
(``user_id`` set, ``thread_id`` NULL), or per-thread (``thread_id`` set).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "132"
down_revision: str | None = "131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_permission_rules",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "search_space_id",
            sa.Integer(),
            sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "thread_id",
            sa.Integer(),
            sa.ForeignKey("new_chat_threads.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.Column(
            "pattern",
            sa.String(length=255),
            nullable=False,
            server_default="*",
        ),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'utc')"),
            index=True,
        ),
        sa.UniqueConstraint(
            "search_space_id",
            "user_id",
            "thread_id",
            "permission",
            "pattern",
            "action",
            name="uq_agent_permission_rules_scope",
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_permission_rules")
