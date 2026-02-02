"""Add public_chat_snapshots table and remove deprecated columns from new_chat_threads

Revision ID: 85
Revises: 84
Create Date: 2026-01-29

Changes:
1. Create public_chat_snapshots table for immutable public chat sharing
2. Drop deprecated columns from new_chat_threads:
   - public_share_token (moved to snapshots)
   - public_share_enabled (replaced by snapshot existence)
   - clone_pending (single-phase clone)
3. Drop related indexes
4. Add cloned_from_snapshot_id to new_chat_threads (tracks source snapshot for clones)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "85"
down_revision: str | None = "84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create public_chat_snapshots table and remove deprecated columns."""

    # 1. Create public_chat_snapshots table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public_chat_snapshots (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            
            -- Link to original thread (CASCADE DELETE)
            thread_id INTEGER NOT NULL
                REFERENCES new_chat_threads(id) ON DELETE CASCADE,
            
            -- Public access token (unique URL identifier)
            share_token VARCHAR(64) NOT NULL UNIQUE,
            
            -- SHA-256 hash of message content for deduplication
            content_hash VARCHAR(64) NOT NULL,
            
            -- Immutable snapshot data (JSONB)
            snapshot_data JSONB NOT NULL,
            
            -- Array of message IDs for cascade delete on edit
            message_ids INTEGER[] NOT NULL,
            
            -- Who created this snapshot
            created_by_user_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            
            -- Prevent duplicate snapshots of same content for same thread
            CONSTRAINT uq_snapshot_thread_content_hash UNIQUE (thread_id, content_hash)
        );
        """
    )

    # 2. Create indexes for public_chat_snapshots
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_public_chat_snapshots_thread_id
        ON public_chat_snapshots(thread_id);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_public_chat_snapshots_share_token
        ON public_chat_snapshots(share_token);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_public_chat_snapshots_content_hash
        ON public_chat_snapshots(content_hash);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_public_chat_snapshots_created_by_user_id
        ON public_chat_snapshots(created_by_user_id);
        """
    )

    # 3. Create GIN index for message_ids array (for fast overlap queries)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_public_chat_snapshots_message_ids
        ON public_chat_snapshots USING GIN(message_ids);
        """
    )

    # 4. Drop deprecated indexes from new_chat_threads
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_public_share_enabled")
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_public_share_token")

    # 5. Drop deprecated columns from new_chat_threads
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS clone_pending")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS public_share_enabled"
    )
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS public_share_token")

    # 6. Add cloned_from_snapshot_id to new_chat_threads
    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS cloned_from_snapshot_id INTEGER
            REFERENCES public_chat_snapshots(id) ON DELETE SET NULL;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_cloned_from_snapshot_id
        ON new_chat_threads(cloned_from_snapshot_id)
        WHERE cloned_from_snapshot_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    """Restore deprecated columns and drop public_chat_snapshots table."""

    # 1. Drop cloned_from_snapshot_id column and index
    op.execute("DROP INDEX IF EXISTS ix_new_chat_threads_cloned_from_snapshot_id")
    op.execute(
        "ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS cloned_from_snapshot_id"
    )

    # 2. Restore deprecated columns on new_chat_threads
    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS public_share_token VARCHAR(64);
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS public_share_enabled BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )

    op.execute(
        """
        ALTER TABLE new_chat_threads
        ADD COLUMN IF NOT EXISTS clone_pending BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )

    # 2. Restore indexes
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_new_chat_threads_public_share_token
        ON new_chat_threads(public_share_token)
        WHERE public_share_token IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_chat_threads_public_share_enabled
        ON new_chat_threads(public_share_enabled)
        WHERE public_share_enabled = TRUE;
        """
    )

    # 3. Drop public_chat_snapshots table and its indexes
    op.execute("DROP INDEX IF EXISTS ix_public_chat_snapshots_message_ids")
    op.execute("DROP INDEX IF EXISTS ix_public_chat_snapshots_created_by_user_id")
    op.execute("DROP INDEX IF EXISTS ix_public_chat_snapshots_content_hash")
    op.execute("DROP INDEX IF EXISTS ix_public_chat_snapshots_share_token")
    op.execute("DROP INDEX IF EXISTS ix_public_chat_snapshots_thread_id")
    op.execute("DROP TABLE IF EXISTS public_chat_snapshots")
