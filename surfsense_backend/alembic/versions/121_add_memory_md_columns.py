"""Add memory_md columns to user and searchspaces tables

Revision ID: 121
Revises: 120

Changes:
1. Add memory_md TEXT column to user table (personal memory)
2. Add shared_memory_md TEXT column to searchspaces table (team memory)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "121"
down_revision: str | None = "120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: column(s) may already exist after a failed run or manual DDL.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'user'
                  AND column_name = 'memory_md'
            ) THEN
                ALTER TABLE "user" ADD COLUMN memory_md TEXT DEFAULT '';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'searchspaces'
                  AND column_name = 'shared_memory_md'
            ) THEN
                ALTER TABLE searchspaces ADD COLUMN shared_memory_md TEXT DEFAULT '';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE searchspaces DROP COLUMN IF EXISTS shared_memory_md")
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS memory_md')
