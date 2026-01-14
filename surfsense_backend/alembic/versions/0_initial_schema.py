"""Initial schema setup

Revision ID: 0
Revises: None

Creates all tables from SQLAlchemy models. Idempotent - safe to run on existing databases.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.db import Base

    connection = op.get_bind()

    # Create tables
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=connection)

    # Set up indexes
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS document_vector_index ON documents USING hnsw (embedding public.vector_cosine_ops)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS document_search_index ON documents USING gin (to_tsvector('english', content))"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS chucks_vector_index ON chunks USING hnsw (embedding public.vector_cosine_ops)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS chucks_search_index ON chunks USING gin (to_tsvector('english', content))"
        )
    )


def downgrade() -> None:
    pass
