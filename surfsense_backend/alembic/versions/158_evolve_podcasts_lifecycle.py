"""evolve podcasts: expand status lifecycle and add brief/transcript/storage columns

Revision ID: 158
Revises: 157
"""

from collections.abc import Sequence

from alembic import op

revision: str = "158"
down_revision: str | None = "157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Retype the status enum by swapping in a fresh type and casting existing
    # rows. The legacy transient value 'generating' maps onto 'rendering'.
    op.execute("ALTER TYPE podcast_status RENAME TO podcast_status_old;")
    op.execute(
        """
        CREATE TYPE podcast_status AS ENUM (
            'pending', 'awaiting_brief', 'drafting', 'awaiting_review',
            'rendering', 'ready', 'failed', 'cancelled'
        );
        """
    )
    op.execute("ALTER TABLE podcasts ALTER COLUMN status DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE podcasts
            ALTER COLUMN status TYPE podcast_status
            USING (
                CASE status::text
                    WHEN 'generating' THEN 'rendering'
                    ELSE status::text
                END
            )::podcast_status;
        """
    )
    op.execute("ALTER TABLE podcasts ALTER COLUMN status SET DEFAULT 'pending';")
    op.execute("DROP TYPE podcast_status_old;")

    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS source_content TEXT;")
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS spec JSONB;")
    op.execute(
        "ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS spec_version "
        "INTEGER NOT NULL DEFAULT 1;"
    )
    op.execute(
        "ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(32);"
    )
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS storage_key TEXT;")
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS duration_seconds INTEGER;")
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS error TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS error;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS duration_seconds;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS storage_key;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS storage_backend;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS spec_version;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS spec;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS source_content;")

    # Collapse the expanded lifecycle back onto the original four values.
    op.execute("ALTER TYPE podcast_status RENAME TO podcast_status_new;")
    op.execute(
        "CREATE TYPE podcast_status AS ENUM "
        "('pending', 'generating', 'ready', 'failed');"
    )
    op.execute("ALTER TABLE podcasts ALTER COLUMN status DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE podcasts
            ALTER COLUMN status TYPE podcast_status
            USING (
                CASE status::text
                    WHEN 'awaiting_brief' THEN 'pending'
                    WHEN 'drafting' THEN 'generating'
                    WHEN 'awaiting_review' THEN 'generating'
                    WHEN 'rendering' THEN 'generating'
                    WHEN 'cancelled' THEN 'failed'
                    ELSE status::text
                END
            )::podcast_status;
        """
    )
    op.execute("ALTER TABLE podcasts ALTER COLUMN status SET DEFAULT 'ready';")
    op.execute("DROP TYPE podcast_status_new;")
