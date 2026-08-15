"""Slim video_presentations into video_presentation_runs and publish to Zero.

The Remotion ``slides`` and ``scene_codes`` now live in the delivered
Artifact's ``artifact_metadata``; the row keeps only the run lifecycle. Run
``backfill_video_artifacts.py --yes`` before this so no slides are lost.

Renames the table, drops the two JSONB working columns, adds ``error`` (a
failed run had no place to record why), and reconciles ``zero_publication`` so
in-flight and failed runs reach the UI by push instead of polling. The
publish is folded in here because nothing happens between the slim and the
publish; the only ordering that matters is the backfill, which brackets this
migration on the far side of 179.

Revision ID: 180
Revises: 179
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from app.zero_publication import apply_publication

revision: str = "180"
down_revision: str | None = "179"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Refuse to drop the working columns while any delivered run has no
    # Artifact: that row's slides/scene_codes would be lost. A clean backfill
    # leaves zero such rows, so this only trips when the ordering was skipped.
    pending = (
        op.get_bind()
        .execute(
            text(
                "SELECT count(*) FROM video_presentations "
                "WHERE status = 'ready' AND artifact_id IS NULL"
            )
        )
        .scalar()
    )
    if pending:
        raise RuntimeError(
            f"{pending} READY video_presentations row(s) have no Artifact. "
            "Run `python -m scripts.backfill_video_artifacts --yes` before this "
            "migration, or their slides/scene_codes will be lost."
        )

    op.execute("ALTER TABLE video_presentations RENAME TO video_presentation_runs")
    op.execute("ALTER TABLE video_presentation_runs DROP COLUMN IF EXISTS slides")
    op.execute("ALTER TABLE video_presentation_runs DROP COLUMN IF EXISTS scene_codes")
    op.execute(
        "ALTER TABLE video_presentation_runs ADD COLUMN IF NOT EXISTS error TEXT"
    )
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
                  AND tablename = 'video_presentation_runs'
            ) THEN
                ALTER PUBLICATION zero_publication
                    DROP TABLE video_presentation_runs;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE video_presentation_runs DROP COLUMN IF EXISTS error")
    op.execute(
        "ALTER TABLE video_presentation_runs ADD COLUMN IF NOT EXISTS slides JSONB"
    )
    op.execute(
        "ALTER TABLE video_presentation_runs ADD COLUMN IF NOT EXISTS scene_codes JSONB"
    )
    op.execute("ALTER TABLE video_presentation_runs RENAME TO video_presentations")
