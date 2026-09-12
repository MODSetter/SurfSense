"""replace provider credentials with endpoint connections

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")
_TEMP_SELECTED = "_selected_models_0004"


def _roles(*values: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name="modelrole",
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(collation="NOCASE"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.CheckConstraint(
            "provider = 'openai_compatible'",
            name=op.f("ck_provider_connections_provider"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_connections")),
        sa.UniqueConstraint("label", name=op.f("uq_provider_connections_label")),
    )

    op.create_table(
        _TEMP_SELECTED,
        sa.Column(
            "role",
            _roles("generation", "image_generation"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.CheckConstraint(
            "(provider = 'ollama' AND connection_id IS NULL) OR "
            "(provider = 'openai_compatible' AND connection_id IS NOT NULL)",
            name=op.f("ck_selected_models_provider_connection"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["provider_connections.id"],
            name=op.f("fk_selected_models_connection_id_provider_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role", name=op.f("pk_selected_models")),
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO {_TEMP_SELECTED} (role, provider, connection_id, name, updated_at)
            SELECT role, provider, NULL, name, updated_at
            FROM selected_models
            WHERE provider = 'ollama' AND role = 'generation'
            """
        )
    )
    op.drop_table("selected_models")
    op.rename_table(_TEMP_SELECTED, "selected_models")
    op.drop_table("provider_credentials")


def downgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("provider", name=op.f("pk_provider_credentials")),
    )

    op.create_table(
        _TEMP_SELECTED,
        sa.Column("role", _roles("generation"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("role", name=op.f("pk_selected_models")),
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO {_TEMP_SELECTED} (role, provider, name, updated_at)
            SELECT role, provider, name, updated_at
            FROM selected_models
            WHERE provider = 'ollama' AND role = 'generation'
            """
        )
    )
    op.drop_table("selected_models")
    op.rename_table(_TEMP_SELECTED, "selected_models")
    op.drop_table("provider_connections")
