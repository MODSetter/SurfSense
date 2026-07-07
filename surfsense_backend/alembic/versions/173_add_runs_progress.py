"""Add runs.progress for streamed scraper run progress.

Stores the coarse (throttled) progress log captured during a run; the live
fine-grained stream stays ephemeral (in-process bus / SSE only). Nullable so
existing rows and the sync/agent doors that don't report progress are unaffected.

Revision ID: 173
Revises: 172
"""

from collections.abc import Sequence

from alembic import op

revision: str = "173"
down_revision: str | None = "172"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS progress JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS progress")
