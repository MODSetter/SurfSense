"""Rename podcasts to podcast_runs, drop the row's audio columns, publish to Zero.

The delivered audio now lives in the Artifact referenced by ``artifact_id``. Run
``backfill_podcast_artifacts.py --yes`` before this so no episode is lost.

Guarded like 180: refuses while any READY row has no Artifact. Renames the
table, drops ``storage_backend`` / ``storage_key`` / ``file_location``, and
reconciles ``zero_publication`` so runs reach the UI by push instead of polling.

Revision ID: 183
Revises: 182
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from app.zero_publication import apply_publication

revision: str = "183"
down_revision: str | None = "182"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pending = (
        op.get_bind()
        .execute(
            text(
                "SELECT count(*) FROM podcasts "
                "WHERE status = 'ready' AND artifact_id IS NULL"
            )
        )
        .scalar()
    )
    if pending:
        raise RuntimeError(
            f"{pending} READY podcasts row(s) have no Artifact. "
            "Run `python -m scripts.backfill_podcast_artifacts --yes` before this "
            "migration, or their audio will be lost."
        )

    op.execute("ALTER TABLE podcasts RENAME TO podcast_runs")
    op.execute("ALTER TABLE podcast_runs DROP COLUMN IF EXISTS storage_backend")
    op.execute("ALTER TABLE podcast_runs DROP COLUMN IF EXISTS storage_key")
    op.execute("ALTER TABLE podcast_runs DROP COLUMN IF EXISTS file_location")
    apply_publication(op.get_bind())


def downgrade() -> None:
    # A published table's columns can't be dropped while the publication
    # depends on them, so release it first.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables
                WHERE pubname = 'zero_publication'
                  AND tablename = 'podcast_runs'
            ) THEN
                ALTER PUBLICATION zero_publication DROP TABLE podcast_runs;
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE podcast_runs ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(32)"
    )
    op.execute("ALTER TABLE podcast_runs ADD COLUMN IF NOT EXISTS storage_key TEXT")
    op.execute("ALTER TABLE podcast_runs ADD COLUMN IF NOT EXISTS file_location TEXT")
    op.execute("ALTER TABLE podcast_runs RENAME TO podcasts")
