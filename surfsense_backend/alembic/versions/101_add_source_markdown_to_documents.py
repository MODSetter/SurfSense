"""101_add_source_markdown_to_documents

Revision ID: 101
Revises: 100
Create Date: 2026-02-17

Adds source_markdown column and converts only documents that have
blocknote_document data. Uses a pure-Python BlockNote JSON → Markdown
converter without external dependencies.

Documents without blocknote_document keep source_markdown = NULL and
get populated lazily by the editor route when a user first opens them.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "101"
down_revision: str | None = "100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.migration.101")


def upgrade() -> None:
    """Add source_markdown column and populate it for existing documents."""

    conn = op.get_bind()
    existing_columns = [
        col["name"] for col in sa.inspect(conn).get_columns("documents")
    ]

    # 1. Add the column
    if "source_markdown" not in existing_columns:
        op.add_column(
            "documents",
            sa.Column("source_markdown", sa.Text(), nullable=True),
        )

    # 2. Convert only documents that have blocknote_document data
    _populate_source_markdown(conn)


def _populate_source_markdown(conn, batch_size: int = 500) -> None:
    """Populate source_markdown only for documents that have blocknote_document.

    Processes in batches to avoid long-running transactions and high memory usage.
    """
    from app.utils.blocknote_to_markdown import blocknote_to_markdown

    # Get total count first
    count_result = conn.execute(
        sa.text("""
            SELECT count(*)
            FROM documents
            WHERE source_markdown IS NULL
              AND blocknote_document IS NOT NULL
        """)
    )
    total = count_result.scalar()

    if total == 0:
        print("No documents with blocknote_document need migration")
        return

    print(
        f"  Migrating {total} documents (with blocknote_document) to source_markdown..."
    )

    migrated = 0
    failed = 0
    offset = 0

    while offset < total:
        # Fetch one batch at a time
        result = conn.execute(
            sa.text("""
                SELECT id, title, blocknote_document
                FROM documents
                WHERE source_markdown IS NULL
                  AND blocknote_document IS NOT NULL
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """),
            {"limit": batch_size, "offset": offset},
        )
        rows = result.fetchall()

        if not rows:
            break

        for row in rows:
            doc_id = row[0]
            doc_title = row[1]
            blocknote_doc = row[2]

            try:
                if isinstance(blocknote_doc, str):
                    blocknote_doc = json.loads(blocknote_doc)
                markdown = blocknote_to_markdown(blocknote_doc)

                if markdown:
                    conn.execute(
                        sa.text("""
                            UPDATE documents SET source_markdown = :md WHERE id = :doc_id
                        """),
                        {"md": markdown, "doc_id": doc_id},
                    )
                    migrated += 1
                else:
                    logger.warning(
                        f"  Doc {doc_id} ({doc_title}): blocknote conversion produced empty result"
                    )
                    failed += 1
            except Exception as e:
                logger.warning(
                    f"  Doc {doc_id} ({doc_title}): blocknote conversion failed ({e})"
                )
                failed += 1

        print(f"  Batch complete: processed {min(offset + batch_size, total)}/{total}")
        offset += batch_size

    print(
        f"source_markdown migration complete: {migrated} migrated, "
        f"{failed} failed out of {total} total"
    )


def downgrade() -> None:
    """Remove source_markdown column."""
    op.drop_column("documents", "source_markdown")
