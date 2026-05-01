"""138_add_thread_auto_model_pinning_fields

Revision ID: 138
Revises: 137
Create Date: 2026-04-30

Add thread-level fields to persist Auto (Fastest) model pinning metadata:
- pinned_llm_config_id: concrete resolved config id used for this thread
- pinned_auto_mode: auto policy identifier (currently "auto_fastest")
- pinned_at: timestamp when the pin was created/refreshed
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
    op.execute(
        "ALTER TABLE new_chat_threads "
        "ADD COLUMN IF NOT EXISTS pinned_auto_mode VARCHAR(32)"
    )
    op.execute(
        "ALTER TABLE new_chat_threads "
        "ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMP WITH TIME ZONE"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_new_chat_threads_pinned_llm_config_id "
        "ON new_chat_threads (pinned_llm_config_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_new_chat_threads_pinned_auto_mode "
        "ON new_chat_threads (pinned_auto_mode)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_pinned_auto_mode")
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_pinned_llm_config_id")

    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS pinned_at")
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS pinned_auto_mode")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS pinned_llm_config_id"
    )
