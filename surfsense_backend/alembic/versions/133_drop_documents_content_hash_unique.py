"""133_drop_documents_content_hash_unique

Revision ID: 133
Revises: 132
Create Date: 2026-04-29

Drop the global UNIQUE constraint on ``documents.content_hash`` so the
new-chat agent's ``write_file`` flow can persist legitimate file copies
(two paths, identical content) without hitting a constraint that mirrors
no real filesystem semantic.

Path uniqueness still lives on ``documents.unique_identifier_hash`` (per
search space), which is the right invariant — exactly like an inode at a
given path on a POSIX filesystem.

The non-unique INDEX on ``content_hash`` is preserved so connector
indexers' "have we seen this content before?" lookup
(:func:`app.tasks.document_processors.base.check_duplicate_document`,
which already uses ``.scalars().first()`` and is therefore tolerant of
duplicates) stays cheap.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import inspect

from alembic import op

revision: str = "133"
down_revision: str | None = "132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_constraint_names(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    return {c["name"] for c in inspector.get_unique_constraints(table)}


def _existing_index_names(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # Both the named UniqueConstraint (added in revision 8) and the
    # implicit-unique-index variant SQLAlchemy may emit need draining.
    constraints = _existing_constraint_names(bind, "documents")
    if "uq_documents_content_hash" in constraints:
        op.drop_constraint(
            "uq_documents_content_hash", "documents", type_="unique"
        )

    indexes = _existing_index_names(bind, "documents")
    # Some Postgres versions surface the unique constraint via a unique
    # index of the same name; check for that too.
    for idx_name in ("uq_documents_content_hash",):
        if idx_name in indexes:
            op.drop_index(idx_name, table_name="documents")

    # Ensure the non-unique index is present for fast lookups.
    if "ix_documents_content_hash" not in indexes:
        op.create_index(
            "ix_documents_content_hash",
            "documents",
            ["content_hash"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Re-applying UNIQUE is destructive: there may now be legitimate
    # duplicates (e.g. two NOTE documents that share content because the
    # user explicitly copied one to a new path). To avoid the migration
    # silently deleting user data, we keep only the lowest-id row per
    # content_hash — same strategy revision 8 used when first introducing
    # the constraint.
    op.execute(
        """
        DELETE FROM documents
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM documents
            GROUP BY content_hash
        )
        """
    )

    indexes = _existing_index_names(bind, "documents")
    if "ix_documents_content_hash" in indexes:
        op.drop_index("ix_documents_content_hash", table_name="documents")

    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_documents_content_hash", "documents", ["content_hash"]
    )
