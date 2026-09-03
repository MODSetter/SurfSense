"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
    ]


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    """Create the tables Local ships with: docs, their chunks, and chat."""
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "document_type",
            _enum("FILE", "NOTE", "ARTIFACT", name="documenttype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum("pending", "processing", "ready", "failed", name="documentstatus"),
            nullable=False,
        ),
        # Set when status is failed: the documents view shows the reason, and
        # cloud's JSONB status blob was the only place that carried it.
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("content", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("dedup_key", sa.String(), nullable=True),
        sa.Column("document_metadata", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_documents_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index("documents_workspace", "documents", ["workspace_id"])
    # Notes carry no dedup key, and SQLite treats every NULL as distinct anyway;
    # the partial index keeps them out rather than relying on that.
    op.create_index(
        "documents_workspace_dedup_key",
        "documents",
        ["workspace_id", "dedup_key"],
        unique=True,
        sqlite_where=sa.text("dedup_key IS NOT NULL"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
    )
    op.create_index(
        "chunks_document_position", "chunks", ["document_id", "position"], unique=True
    )

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_chat_threads_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_threads")),
    )
    op.create_index("chat_threads_workspace", "chat_threads", ["workspace_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_thread_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            _enum("user", "assistant", "system", name="messagerole"),
            nullable=False,
        ),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_thread_id"],
            ["chat_threads.id"],
            name=op.f("fk_chat_messages_chat_thread_id_chat_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        "chat_messages_thread", "chat_messages", ["chat_thread_id", "created_at"]
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("chat_thread_id", sa.Integer(), nullable=True),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("updated_by_tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_artifacts_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_artifacts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chat_thread_id"],
            ["chat_threads.id"],
            name=op.f("fk_artifacts_chat_thread_id_chat_threads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint("document_id", name=op.f("uq_artifacts_document_id")),
        sa.CheckConstraint(
            "generation > 0", name=op.f("ck_artifacts_generation_positive")
        ),
    )
    op.create_index("artifacts_workspace", "artifacts", ["workspace_id"])
    op.create_index("artifacts_chat_thread", "artifacts", ["chat_thread_id"])

    op.create_table(
        "artifact_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", _enum("primary", "preview", name="artifactfilerole"), nullable=False
        ),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_artifact_files_artifact_id_artifacts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_files")),
        sa.UniqueConstraint(
            "artifact_id", "role", name=op.f("uq_artifact_files_artifact_id")
        ),
        sa.UniqueConstraint("storage_key", name=op.f("uq_artifact_files_storage_key")),
        sa.CheckConstraint(
            "size_bytes > 0", name=op.f("ck_artifact_files_size_positive")
        ),
    )


def downgrade() -> None:
    """Drop in dependency order; SQLite refuses to drop a referenced parent."""
    op.drop_table("artifact_files")
    op.drop_table("artifacts")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("workspaces")
