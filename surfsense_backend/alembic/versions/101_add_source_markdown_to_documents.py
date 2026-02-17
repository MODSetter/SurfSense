"""101_add_source_markdown_to_documents

Revision ID: 101
Revises: 100
Create Date: 2026-02-17

Adds source_markdown column and populates it for existing documents
using a pure-Python BlockNote JSON → Markdown converter. No external
dependencies (no Node.js, no Celery, no HTTP calls).

Fallback chain per document:
  1. blocknote_document exists → convert to markdown with Python converter
  2. blocknote_document missing/fails → reconstruct from chunks
  3. Neither exists → skip (log warning)
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

    # 2. Populate source_markdown for existing documents (inline, synchronous)
    _populate_source_markdown(conn)


def _populate_source_markdown(conn) -> None:
    """Populate source_markdown for all documents where it is NULL.

    Fallback chain:
        1. blocknote_document → pure-Python converter → source_markdown
        2. chunks (ordered by id) → joined text → source_markdown
        3. Neither → skip with warning
    """
    # Import the pure-Python converter (no external deps)
    from app.utils.blocknote_to_markdown import blocknote_to_markdown

    # Find documents that need migration
    result = conn.execute(
        sa.text("""
            SELECT id, title, blocknote_document
            FROM documents
            WHERE source_markdown IS NULL
        """)
    )
    rows = result.fetchall()

    total = len(rows)
    if total == 0:
        print("✓ No documents need source_markdown migration")
        return

    print(f"  Migrating {total} documents to source_markdown...")

    migrated = 0
    from_blocknote = 0
    from_chunks = 0
    skipped = 0

    for row in rows:
        doc_id = row[0]
        doc_title = row[1]
        blocknote_doc = row[2]

        markdown = None

        # --- Fallback 1: Convert blocknote_document with pure Python ---
        if blocknote_doc:
            try:
                # blocknote_doc may be a JSON string or already parsed
                if isinstance(blocknote_doc, str):
                    blocknote_doc = json.loads(blocknote_doc)
                markdown = blocknote_to_markdown(blocknote_doc)
                if markdown:
                    from_blocknote += 1
            except Exception as e:
                logger.warning(
                    f"  Doc {doc_id} ({doc_title}): blocknote conversion failed ({e}), "
                    f"falling back to chunks"
                )

        # --- Fallback 2: Reconstruct from chunks ---
        if not markdown:
            chunk_result = conn.execute(
                sa.text("""
                    SELECT content FROM chunks
                    WHERE document_id = :doc_id
                    ORDER BY id
                """),
                {"doc_id": doc_id},
            )
            chunk_rows = chunk_result.fetchall()
            if chunk_rows:
                chunk_texts = [r[0] for r in chunk_rows if r[0]]
                if chunk_texts:
                    markdown = "\n\n".join(chunk_texts)
                    from_chunks += 1

        # --- Fallback 3: Nothing to migrate from ---
        if not markdown or not markdown.strip():
            logger.warning(
                f"  Doc {doc_id} ({doc_title}): no blocknote_document or chunks — skipped"
            )
            skipped += 1
            continue

        # Write source_markdown
        conn.execute(
            sa.text("""
                UPDATE documents SET source_markdown = :md WHERE id = :doc_id
            """),
            {"md": markdown, "doc_id": doc_id},
        )
        migrated += 1

    print(
        f"✓ source_markdown migration complete: {migrated} migrated "
        f"({from_blocknote} from blocknote, {from_chunks} from chunks), "
        f"{skipped} skipped out of {total} total"
    )


def downgrade() -> None:
    """Remove source_markdown column."""
    op.drop_column("documents", "source_markdown")
