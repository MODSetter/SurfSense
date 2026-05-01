"""138_add_thread_auto_model_pinning_fields

Revision ID: 138
Revises: 137
Create Date: 2026-04-30

Add a single thread-level column to persist the Auto (Fastest) model pin:
- pinned_llm_config_id: concrete resolved global LLM config id used for this
  thread. NULL means "no pin; Auto will resolve on next turn".

The column is unindexed: all reads are by new_chat_threads.id (primary key),
so a secondary index would be dead write amplification.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "138"
down_revision: str | None = "137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE new_chat_threads "
        "ADD COLUMN IF NOT EXISTS pinned_llm_config_id INTEGER"
    )


def downgrade() -> None:
    # Drop any shape the thread row may be carrying. The extra columns and
    # indexes only exist on dev DBs that ran an earlier draft of 138; IF EXISTS
    # makes each statement a safe no-op on the lean shape.
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_pinned_auto_mode")
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_pinned_llm_config_id")
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS pinned_at")
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS pinned_auto_mode")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS pinned_llm_config_id"
    )
