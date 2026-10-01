"""Record which embedding model built the index.

An existing library was built by the bundled bge-small, so it gets that row,
pointing at the vectors it already has; nothing is re-embedded. A fresh install
gets no row: onboarding offers the choice and writes it.

The spec is written out here rather than imported, so this revision means the
same thing whatever the app's own copy of bge's spec later becomes.

`documents` gains its column by a plain ALTER TABLE, never batch mode: a batch
rebuild drops the table, and with foreign keys on that cascades to every chunk.

Revision ID: 0021
Revises: 0020
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BGE = {
    "id": "bge-small-en-v1.5",
    "source": "curated",
    "identified": "measured",
    "repo": "Qdrant/bge-small-en-v1.5-onnx-Q",
    "revision": "aa8f8b060edb00e03bfdd08813a2949946c8ba55",
    "weights": {
        "path": "model_optimized.onnx",
        "sha256": "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431",
    },
    "tokenizer": {
        "path": "tokenizer.json",
        "sha256": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    },
    "dimension": 384,
    "pooling": "cls",
    "normalize": True,
    "query_prefix": "",
    "document_prefix": "",
    "max_tokens": 512,
    "semantic_weight": 0.65,
}


def upgrade() -> None:
    op.create_table(
        "embedding_indexes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("vector_table", sa.String(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "active",
                "building",
                "retired",
                name="indexstate",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding_indexes")),
    )
    # Inline, because Alembic will not add a constraint to a SQLite table and
    # SQLite accepts a reference on an added column only in the column itself.
    op.execute(
        "ALTER TABLE documents ADD COLUMN embedding_index_id INTEGER "
        "CONSTRAINT fk_documents_embedding_index_id_embedding_indexes "
        "REFERENCES embedding_indexes (id)"
    )

    bind = op.get_bind()
    built = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM onboarding_completion) "
            "OR EXISTS (SELECT 1 FROM chunks)"
        )
    ).scalar_one()
    if not built:
        return

    index_id = bind.execute(
        sa.text(
            "INSERT INTO embedding_indexes(spec, vector_table, state) "
            "VALUES (:spec, 'chunk_vectors', 'active') RETURNING id"
        ),
        {"spec": json.dumps(_BGE)},
    ).scalar_one()
    # Only what is indexed; a document still waiting is stamped by its ingest.
    bind.execute(
        sa.text(
            "UPDATE documents SET embedding_index_id = :id "
            "WHERE id IN (SELECT DISTINCT document_id FROM chunks)"
        ),
        {"id": index_id},
    )


def downgrade() -> None:
    op.drop_column("documents", "embedding_index_id")
    op.drop_table("embedding_indexes")
