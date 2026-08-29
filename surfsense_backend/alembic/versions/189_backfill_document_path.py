"""Backfill documents.path from the legacy virtual_path marker.

Ownership and resolution now key on ``documents.path``. Rows written before the
column existed carry the path only on their ``document_metadata`` marker; copy
it into the column so those rows are found by the column, not the marker. Guards
match ``recorded_virtual_path``: fill only an empty column, only from a
``/documents`` marker, never overwriting an authored path.

Revision ID: 189
Revises: 188
"""

from collections.abc import Sequence

from alembic import op

revision: str = "189"
down_revision: str | None = "188"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE documents SET path = document_metadata ->> 'virtual_path' "
        "WHERE path IS NULL "
        "AND document_metadata ->> 'virtual_path' LIKE '/documents/%'"
    )


def downgrade() -> None:
    # A backfilled column is indistinguishable from one a writer set natively, so
    # there is nothing safe to undo.
    pass
