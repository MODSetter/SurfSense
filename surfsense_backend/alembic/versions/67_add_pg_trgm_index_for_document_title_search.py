"""Add pg_trgm indexes for efficient document title search

Revision ID: 67
Revises: 66

Adds the pg_trgm extension and GIN trigram indexes on documents.title
to enable efficient ILIKE searches with leading wildcards (e.g., '%search_term%').

Indexes added:
1. idx_documents_title_trgm - GIN trigram on title for ILIKE '%term%'
2. idx_documents_search_space_id - B-tree on search_space_id for filtering
3. idx_documents_search_space_updated - Composite for recent docs query (covering index)
4. idx_surfsense_docs_title_trgm - GIN trigram on surfsense docs title

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "67"
down_revision: str | None = "66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add pg_trgm extension and optimized indexes for document search."""

    # Create pg_trgm extension if not exists
    # This extension provides trigram-based text similarity functions and operators
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 1. GIN trigram index on documents.title for ILIKE '%term%' searches
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_title_trgm 
        ON documents USING gin (title gin_trgm_ops);
        """
    )

    # 2. B-tree index on search_space_id for fast filtering
    # (Every query filters by search_space_id first)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_search_space_id 
        ON documents (search_space_id);
        """
    )

    # 3. Covering index for "recent documents" query (no search term)
    # Includes id, title, document_type so PostgreSQL can do index-only scan
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_search_space_updated 
        ON documents (search_space_id, updated_at DESC NULLS LAST)
        INCLUDE (id, title, document_type);
        """
    )

    # 4. GIN trigram index on surfsense_docs_documents.title
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_surfsense_docs_title_trgm 
        ON surfsense_docs_documents USING gin (title gin_trgm_ops);
        """
    )


def downgrade() -> None:
    """Remove all document search indexes (extension is left in place)."""
    op.execute("DROP INDEX IF EXISTS idx_surfsense_docs_title_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_documents_search_space_updated;")
    op.execute("DROP INDEX IF EXISTS idx_documents_search_space_id;")
    op.execute("DROP INDEX IF EXISTS idx_documents_title_trgm;")
