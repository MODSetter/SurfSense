"""134_add_thread_auto_model_pinning_fields

Revision ID: 134
Revises: 133
Create Date: 2026-04-29

Add thread-level fields to persist Auto (Fastest) model pinning metadata:
- pinned_llm_config_id: concrete resolved config id used for this thread
- pinned_auto_mode: auto policy identifier (currently "auto_fastest")
- pinned_at: timestamp when the pin was created/refreshed
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "134"
down_revision: str | None = "133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "new_chat_threads",
        sa.Column("pinned_llm_config_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "new_chat_threads",
        sa.Column("pinned_auto_mode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "new_chat_threads",
        sa.Column("pinned_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_new_chat_threads_pinned_llm_config_id",
        "new_chat_threads",
        ["pinned_llm_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_new_chat_threads_pinned_auto_mode",
        "new_chat_threads",
        ["pinned_auto_mode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_new_chat_threads_pinned_auto_mode", table_name="new_chat_threads")
    op.drop_index(
        "ix_new_chat_threads_pinned_llm_config_id", table_name="new_chat_threads"
    )

    op.drop_column("new_chat_threads", "pinned_at")
    op.drop_column("new_chat_threads", "pinned_auto_mode")
    op.drop_column("new_chat_threads", "pinned_llm_config_id")
