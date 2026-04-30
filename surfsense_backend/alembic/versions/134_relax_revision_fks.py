"""134_relax_revision_fks

Revision ID: 134
Revises: 133
Create Date: 2026-04-29

Relax the parent FKs on ``document_revisions`` and ``folder_revisions`` so
revisions survive the deletes they describe.

Why: the snapshot/revert pipeline writes a ``DocumentRevision`` BEFORE
hard-deleting a document via the ``rm`` tool (and likewise a
``FolderRevision`` before ``rmdir``). If the FK is ``ON DELETE CASCADE``
the snapshot row is wiped at the exact moment we need it most — revert
then has nothing to read and the operation becomes irreversible.

Migration:

* ``document_revisions.document_id``: ``NOT NULL`` -> nullable; FK
  ``ON DELETE CASCADE`` -> ``ON DELETE SET NULL``.
* ``folder_revisions.folder_id``: same treatment.

The ``search_space_id`` FK on both tables is left unchanged (still
``ON DELETE CASCADE``). When a search space is deleted, all documents,
folders, AND their revisions go together — that's the correct teardown
story.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "134"
down_revision: str | None = "133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk_name(bind, table: str, column: str) -> str | None:
    """Return the (single) FK constraint name on ``table.column``, if any."""
    inspector = inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        cols = fk.get("constrained_columns") or []
        if cols == [column]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()

    # --- document_revisions.document_id -> nullable + SET NULL ---------------
    fk_name = _fk_name(bind, "document_revisions", "document_id")
    if fk_name:
        op.drop_constraint(fk_name, "document_revisions", type_="foreignkey")
    op.alter_column(
        "document_revisions",
        "document_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_foreign_key(
        "document_revisions_document_id_fkey",
        "document_revisions",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- folder_revisions.folder_id -> nullable + SET NULL -------------------
    fk_name = _fk_name(bind, "folder_revisions", "folder_id")
    if fk_name:
        op.drop_constraint(fk_name, "folder_revisions", type_="foreignkey")
    op.alter_column(
        "folder_revisions",
        "folder_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_foreign_key(
        "folder_revisions_folder_id_fkey",
        "folder_revisions",
        "folders",
        ["folder_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Reinstating NOT NULL + CASCADE requires draining orphan rows first
    # (any revision whose parent doc/folder has already been deleted).
    op.execute("DELETE FROM document_revisions WHERE document_id IS NULL")
    op.execute("DELETE FROM folder_revisions WHERE folder_id IS NULL")

    # --- document_revisions.document_id -> NOT NULL + CASCADE ---------------
    fk_name = _fk_name(bind, "document_revisions", "document_id")
    if fk_name:
        op.drop_constraint(fk_name, "document_revisions", type_="foreignkey")
    op.alter_column(
        "document_revisions",
        "document_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "document_revisions_document_id_fkey",
        "document_revisions",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- folder_revisions.folder_id -> NOT NULL + CASCADE -------------------
    fk_name = _fk_name(bind, "folder_revisions", "folder_id")
    if fk_name:
        op.drop_constraint(fk_name, "folder_revisions", type_="foreignkey")
    op.alter_column(
        "folder_revisions",
        "folder_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "folder_revisions_folder_id_fkey",
        "folder_revisions",
        "folders",
        ["folder_id"],
        ["id"],
        ondelete="CASCADE",
    )
