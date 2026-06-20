"""add chunks.start_char/end_char for citation offsets

Char offsets into the document's source_markdown (half-open span) let citations
resolve the exact passage a chunk came from. Nullable because historical rows
have no span; they populate on the next connector sync or user edit/reindex.

No backfill: a bulk UPDATE of every chunk on a large HNSW-indexed table rewrites
every secondary index per row (see migration 165 for the same reasoning).

Revision ID: 166
Revises: 165
"""

from collections.abc import Sequence

from alembic import op

revision: str = "166"
down_revision: str | None = "165"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS start_char INTEGER;")
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS end_char INTEGER;")


def downgrade() -> None:
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS end_char;")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS start_char;")
