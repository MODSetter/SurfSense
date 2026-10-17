"""Record which engine runs each agent thread, and keep a Claude Code session's transcript and account.

Plain ALTER TABLE: rebuilding chat_threads with foreign keys enabled would
cascade-delete its messages. Every agent thread so far ran on opencode.

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chat_threads ADD COLUMN agent_engine VARCHAR(11) "
        "CONSTRAINT ck_chat_threads_agentenginekind "
        "CHECK (agent_engine IN ('opencode', 'claude_code'))"
    )
    op.execute(
        "UPDATE chat_threads SET agent_engine = 'opencode' "
        "WHERE opencode_session_id IS NOT NULL"
    )
    op.add_column(
        "chat_threads", sa.Column("claude_session_id", sa.String(), nullable=True)
    )
    op.add_column(
        "chat_threads", sa.Column("claude_account", sa.String(), nullable=True)
    )
    op.create_table(
        "claude_session_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("uuid", sa.String(), nullable=True),
        sa.Column("entry", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name=op.f("fk_claude_session_entries_thread_id_chat_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claude_session_entries")),
    )
    op.create_index(
        "claude_session_entries_session_uuid",
        "claude_session_entries",
        ["session_id", "uuid"],
        unique=True,
    )
    op.create_index(
        "claude_session_entries_thread", "claude_session_entries", ["thread_id"]
    )
    op.create_table(
        "claude_reply_endings",
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("reply_id", sa.String(), nullable=False),
        sa.Column("ending", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name=op.f("fk_claude_reply_endings_thread_id_chat_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "thread_id", "reply_id", name=op.f("pk_claude_reply_endings")
        ),
    )


def downgrade() -> None:
    op.drop_table("claude_reply_endings")
    op.drop_index("claude_session_entries_thread", table_name="claude_session_entries")
    op.drop_index(
        "claude_session_entries_session_uuid", table_name="claude_session_entries"
    )
    op.drop_table("claude_session_entries")
    op.drop_column("chat_threads", "claude_account")
    op.drop_column("chat_threads", "claude_session_id")
    op.drop_column("chat_threads", "agent_engine")
