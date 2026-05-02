"""136_new_chat_message_turn_id

Revision ID: 136
Revises: 135
Create Date: 2026-04-29

Persist the per-turn correlation id on each chat message.

Background
----------
LangGraph's checkpointer stores user-provided ``configurable.turn_id``
in checkpoint metadata (see
``langgraph/checkpoint/base/__init__.py:get_checkpoint_metadata``). To
support edit-from-arbitrary-position, the regenerate route needs to map
a ``message_id`` -> ``turn_id`` -> checkpoint at request time. Without
this column the mapping doesn't exist anywhere, so regenerate would
have to hardcode the "last 2 messages" rewind heuristic.

This migration adds a nullable ``turn_id`` column to ``new_chat_messages``
plus an index. Legacy rows have NULL — the regenerate route degrades
gracefully to the reload-last-two heuristic for those.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "136"
down_revision: str | None = "135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "new_chat_messages",
        sa.Column("turn_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_new_chat_messages_turn_id",
        "new_chat_messages",
        ["turn_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_new_chat_messages_turn_id", table_name="new_chat_messages")
    op.drop_column("new_chat_messages", "turn_id")
