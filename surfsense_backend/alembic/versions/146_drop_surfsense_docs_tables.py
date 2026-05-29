"""Drop Surfsense docs tables (feature removed end to end)

Revision ID: 146
Revises: 145
Create Date: 2026-05-28

Removes the SurfSense product-documentation feature: the
``surfsense_docs_documents`` and ``surfsense_docs_chunks`` tables (created
in revision 60) and the GIN trigram index on the title column (added in
revision 67). The docs were seeded at startup from local MDX files, so no
user data is lost. Downgrade recreates the tables and indexes.
"""

from collections.abc import Sequence

from alembic import op
from app.config import config

# revision identifiers, used by Alembic.
revision: str = "146"
down_revision: str | None = "145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Embedding dimension is required to recreate the vector columns on downgrade.
EMBEDDING_DIM = config.embedding_model_instance.dimension


def upgrade() -> None:
    """Drop surfsense docs tables and all their indexes."""
    # Trigram index from revision 67
    op.execute("DROP INDEX IF EXISTS idx_surfsense_docs_title_trgm")

    # Full-text search indexes
    op.execute("DROP INDEX IF EXISTS surfsense_docs_chunks_search_index")
    op.execute("DROP INDEX IF EXISTS surfsense_docs_documents_search_index")

    # Vector indexes
    op.execute("DROP INDEX IF EXISTS surfsense_docs_chunks_vector_index")
    op.execute("DROP INDEX IF EXISTS surfsense_docs_documents_vector_index")

    # B-tree indexes
    op.execute("DROP INDEX IF EXISTS ix_surfsense_docs_chunks_document_id")
    op.execute("DROP INDEX IF EXISTS ix_surfsense_docs_documents_updated_at")
    op.execute("DROP INDEX IF EXISTS ix_surfsense_docs_documents_content_hash")
    op.execute("DROP INDEX IF EXISTS ix_surfsense_docs_documents_source")

    # Tables (chunks first due to FK)
    op.execute("DROP TABLE IF EXISTS surfsense_docs_chunks")
    op.execute("DROP TABLE IF EXISTS surfsense_docs_documents")


def downgrade() -> None:
    """Recreate surfsense docs tables and indexes (reverses revisions 60 + 67)."""
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS surfsense_docs_documents (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            source VARCHAR NOT NULL UNIQUE,
            title VARCHAR NOT NULL,
            content TEXT NOT NULL,
            content_hash VARCHAR NOT NULL,
            embedding vector({EMBEDDING_DIM}),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS surfsense_docs_chunks (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}),
            document_id INTEGER NOT NULL REFERENCES surfsense_docs_documents(id) ON DELETE CASCADE
        );
        """
    )

    # B-tree indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_surfsense_docs_documents_source ON surfsense_docs_documents(source)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_surfsense_docs_documents_content_hash ON surfsense_docs_documents(content_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_surfsense_docs_documents_updated_at ON surfsense_docs_documents(updated_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_surfsense_docs_chunks_document_id ON surfsense_docs_chunks(document_id)"
    )

    # Vector indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS surfsense_docs_documents_vector_index
        ON surfsense_docs_documents USING hnsw (embedding public.vector_cosine_ops);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS surfsense_docs_chunks_vector_index
        ON surfsense_docs_chunks USING hnsw (embedding public.vector_cosine_ops);
        """
    )

    # Full-text search indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS surfsense_docs_documents_search_index
        ON surfsense_docs_documents USING gin (to_tsvector('english', content));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS surfsense_docs_chunks_search_index
        ON surfsense_docs_chunks USING gin (to_tsvector('english', content));
        """
    )

    # Trigram index from revision 67
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_surfsense_docs_title_trgm
        ON surfsense_docs_documents USING gin (title gin_trgm_ops);
        """
    )
