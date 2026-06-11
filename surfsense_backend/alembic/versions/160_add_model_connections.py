"""add model connections

Revision ID: 160
Revises: 159
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "160"
down_revision: str | None = "159"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return index_name in {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    }


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _add_searchspace_column_if_missing(column_name: str) -> None:
    if not _column_exists("searchspaces", column_name):
        op.add_column("searchspaces", sa.Column(column_name, sa.Integer(), nullable=True))


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    connection_scope.create(bind, checkfirst=True)
    model_source.create(bind, checkfirst=True)

    if _table_exists("connections"):
        if _column_exists("connections", "litellm_provider") and not _column_exists(
            "connections", "provider"
        ):
            op.alter_column(
                "connections",
                "litellm_provider",
                new_column_name="provider",
                existing_type=sa.String(length=100),
                existing_nullable=True,
            )
            op.alter_column(
                "connections",
                "provider",
                existing_type=sa.String(length=100),
                nullable=False,
            )
        elif _column_exists("connections", "native_provider") and not _column_exists(
            "connections", "provider"
        ):
            op.alter_column(
                "connections",
                "native_provider",
                new_column_name="provider",
                existing_type=sa.String(length=100),
                existing_nullable=True,
            )
            op.alter_column(
                "connections",
                "provider",
                existing_type=sa.String(length=100),
                nullable=False,
            )
        elif not _column_exists("connections", "provider"):
            op.add_column(
                "connections",
                sa.Column("provider", sa.String(length=100), nullable=False),
            )
        _drop_index_if_exists("connections", "ix_connections_protocol")
        _drop_column_if_exists("connections", "protocol")
    else:
        op.create_table(
            "connections",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("provider", sa.String(length=100), nullable=False),
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
    if _index_exists("connections", "ix_connections_native_provider") and not _index_exists(
        "connections", "ix_connections_provider"
    ):
        op.execute(
            "ALTER INDEX ix_connections_native_provider "
            "RENAME TO ix_connections_provider"
        )
    if _index_exists("connections", "ix_connections_litellm_provider") and not _index_exists(
        "connections", "ix_connections_provider"
    ):
        op.execute(
            "ALTER INDEX ix_connections_litellm_provider "
            "RENAME TO ix_connections_provider"
        )
    _create_index_if_missing("ix_connections_provider", "connections", ["provider"])
    _create_index_if_missing("ix_connections_scope", "connections", ["scope"])

    if not _table_exists("models"):
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
            sa.Column("supports_chat", sa.Boolean(), nullable=True),
            sa.Column("max_input_tokens", sa.Integer(), nullable=True),
            sa.Column("supports_image_input", sa.Boolean(), nullable=True),
            sa.Column("supports_tools", sa.Boolean(), nullable=True),
            sa.Column("supports_image_generation", sa.Boolean(), nullable=True),
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
    else:
        if not _column_exists("models", "supports_chat"):
            op.add_column("models", sa.Column("supports_chat", sa.Boolean(), nullable=True))
        if not _column_exists("models", "max_input_tokens"):
            op.add_column("models", sa.Column("max_input_tokens", sa.Integer(), nullable=True))
        if not _column_exists("models", "supports_image_input"):
            op.add_column(
                "models", sa.Column("supports_image_input", sa.Boolean(), nullable=True)
            )
        if not _column_exists("models", "supports_tools"):
            op.add_column("models", sa.Column("supports_tools", sa.Boolean(), nullable=True))
        if not _column_exists("models", "supports_image_generation"):
            op.add_column(
                "models", sa.Column("supports_image_generation", sa.Boolean(), nullable=True)
            )
        _drop_column_if_exists("models", "capabilities")
        _drop_column_if_exists("models", "capabilities_declared")
        _drop_column_if_exists("models", "capabilities_verified")
    _create_index_if_missing("ix_models_connection_id", "models", ["connection_id"])
    _create_index_if_missing("ix_models_model_id", "models", ["model_id"])
    _create_index_if_missing("ix_models_billing_tier", "models", ["billing_tier"])

    _add_searchspace_column_if_missing("chat_model_id")
    _add_searchspace_column_if_missing("image_gen_model_id")
    _add_searchspace_column_if_missing("vision_model_id")

    op.execute("DROP TYPE IF EXISTS connectionprotocol")


def downgrade() -> None:
    op.drop_column("searchspaces", "vision_model_id")
    op.drop_column("searchspaces", "image_gen_model_id")
    op.drop_column("searchspaces", "chat_model_id")

    op.drop_index(op.f("ix_models_billing_tier"), table_name="models")
    op.drop_index("ix_models_model_id", table_name="models")
    op.drop_index(op.f("ix_models_connection_id"), table_name="models")
    op.drop_table("models")

    op.drop_index(op.f("ix_connections_scope"), table_name="connections")
    op.drop_index(op.f("ix_connections_provider"), table_name="connections")
    op.drop_table("connections")

    bind = op.get_bind()
    model_source.drop(bind, checkfirst=True)
    connection_scope.drop(bind, checkfirst=True)
