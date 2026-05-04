"""141_unique_chat_message_turn_role

Revision ID: 141
Revises: 140
Create Date: 2026-05-04

Add a partial unique index on ``new_chat_messages(thread_id, turn_id, role)``
where ``turn_id IS NOT NULL``.

Why
---
The streaming chat path (`stream_new_chat` / `stream_resume_chat`) is being
moved to write its own ``new_chat_messages`` rows server-side instead of
relying on the frontend's later ``POST /threads/{id}/messages`` call. This
closes the "ghost-thread" abuse vector where authenticated callers got free
LLM completions while ``new_chat_messages`` stayed empty.

For server-side and legacy frontend writes to coexist we need an idempotency
key. The natural triple is ``(thread_id, turn_id, role)``: the server issues
exactly one ``turn_id`` per turn, and a turn produces at most one user
message and one assistant message. Whichever side wins the race writes the
row; the loser hits ``IntegrityError`` and recovers gracefully.

Partial — ``WHERE turn_id IS NOT NULL`` — so:

  * Legacy rows that predate the ``turn_id`` column (migration 136) keep
    co-existing without de-dup.
  * Clone / snapshot inserts in
    ``app/services/public_chat_service.py`` that build ``NewChatMessage``
    without ``turn_id`` are unaffected (multiple snapshot copies of the same
    user/assistant pair are intentional).

This index coexists with the existing single-column ``ix_new_chat_messages_turn_id``
from migration 136 — no collision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "141"
down_revision: str | None = "140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "uq_new_chat_messages_thread_turn_role"
TABLE_NAME = "new_chat_messages"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["thread_id", "turn_id", "role"],
        unique=True,
        postgresql_where=sa.text("turn_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
