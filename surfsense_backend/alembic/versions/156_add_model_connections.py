"""add model connections

Revision ID: 156
Revises: 155
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "156"
down_revision: str | None = "155"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


connection_protocol = postgresql.ENUM(
    "OLLAMA",
    "OPENAI_COMPATIBLE",
    "NATIVE",
    name="connectionprotocol",
    create_type=False,
)
connection_scope = postgresql.ENUM(
    "GLOBAL",
    "SEARCH_SPACE",
    "USER",
    name="connectionscope",
    create_type=False,
)
model_source = postgresql.ENUM(
    "DISCOVERED",
    "MANUAL",
    name="modelsource",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    connection_protocol.create(bind, checkfirst=True)
    connection_scope.create(bind, checkfirst=True)
    model_source.create(bind, checkfirst=True)

    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protocol", connection_protocol, nullable=False),
        sa.Column("native_provider", sa.String(length=100), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("scope", connection_scope, nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("search_space_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("last_verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=50), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(scope = 'GLOBAL' AND search_space_id IS NULL AND user_id IS NULL) OR "
            "(scope = 'SEARCH_SPACE' AND search_space_id IS NOT NULL AND user_id IS NOT NULL) OR "
            "(scope = 'USER' AND user_id IS NOT NULL)",
            name="ck_connections_scope_owner",
        ),
        sa.ForeignKeyConstraint(
            ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_connections_protocol"), "connections", ["protocol"], unique=False)
    op.create_index(
        op.f("ix_connections_native_provider"),
        "connections",
        ["native_provider"],
        unique=False,
    )
    op.create_index(op.f("ix_connections_scope"), "connections", ["scope"], unique=False)

    op.create_table(
        "models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "source",
            model_source,
            server_default="DISCOVERED",
            nullable=False,
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "capabilities_declared",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "capabilities_verified",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "capabilities_override",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("billing_tier", sa.String(length=50), nullable=True),
        sa.Column(
            "catalog",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id", "model_id", name="uq_models_connection_model_id"
        ),
    )
    op.create_index(op.f("ix_models_connection_id"), "models", ["connection_id"], unique=False)
    op.create_index("ix_models_model_id", "models", ["model_id"], unique=False)
    op.create_index(op.f("ix_models_billing_tier"), "models", ["billing_tier"], unique=False)

    op.add_column(
        "searchspaces",
        sa.Column("chat_model_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "searchspaces",
        sa.Column("image_gen_model_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "searchspaces",
        sa.Column("vision_model_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("searchspaces", "vision_model_id")
    op.drop_column("searchspaces", "image_gen_model_id")
    op.drop_column("searchspaces", "chat_model_id")

    op.drop_index(op.f("ix_models_billing_tier"), table_name="models")
    op.drop_index("ix_models_model_id", table_name="models")
    op.drop_index(op.f("ix_models_connection_id"), table_name="models")
    op.drop_table("models")

    op.drop_index(op.f("ix_connections_scope"), table_name="connections")
    op.drop_index(op.f("ix_connections_native_provider"), table_name="connections")
    op.drop_index(op.f("ix_connections_protocol"), table_name="connections")
    op.drop_table("connections")

    bind = op.get_bind()
    model_source.drop(bind, checkfirst=True)
    connection_scope.drop(bind, checkfirst=True)
    connection_protocol.drop(bind, checkfirst=True)
