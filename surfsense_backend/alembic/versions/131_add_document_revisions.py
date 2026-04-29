"""131_add_document_revisions

Revision ID: 131
Revises: 130
Create Date: 2026-04-28

Adds two snapshot tables that back the per-action revert flow:

* ``document_revisions``: pre-mutation snapshot of NOTE/FILE/EXTENSION docs.
* ``folder_revisions``: pre-mutation snapshot of folder mkdir/move/delete.

Both are written by :class:`KnowledgeBasePersistenceMiddleware` ahead of
state-changing tool calls and consumed by ``revert_service.revert_action``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "131"
down_revision: str | None = "130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "search_space_id",
            sa.Integer(),
            sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("content_before", sa.Text(), nullable=True),
        sa.Column("title_before", sa.String(), nullable=True),
        sa.Column("folder_id_before", sa.Integer(), nullable=True),
        sa.Column(
            "chunks_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "metadata_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_by_turn_id", sa.String(length=64), nullable=True, index=True
        ),
        sa.Column(
            "agent_action_id",
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

    op.create_table(
        "folder_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "search_space_id",
            sa.Integer(),
            sa.ForeignKey("searchspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name_before", sa.String(length=255), nullable=True),
        sa.Column("parent_id_before", sa.Integer(), nullable=True),
        sa.Column("position_before", sa.String(length=50), nullable=True),
        sa.Column(
            "created_by_turn_id", sa.String(length=64), nullable=True, index=True
        ),
        sa.Column(
            "agent_action_id",
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


def downgrade() -> None:
    op.drop_table("folder_revisions")
    op.drop_table("document_revisions")
