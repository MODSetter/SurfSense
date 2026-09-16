"""let the bundled image runtime hold a role

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-15

selected_models only admitted 'ollama' (no connection) or 'openai_compatible'
(with one), so choosing the local image model failed the check constraint and
the write surfaced as a 500. sd-server is local and connectionless like Ollama.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")
_TEMP = "_selected_models_0009"

LOCAL_AND_REMOTE = (
    "(provider IN ('ollama', 'sdcpp') AND connection_id IS NULL) OR "
    "(provider = 'openai_compatible' AND connection_id IS NOT NULL)"
)
OLLAMA_AND_REMOTE = (
    "(provider = 'ollama' AND connection_id IS NULL) OR "
    "(provider = 'openai_compatible' AND connection_id IS NOT NULL)"
)


def _rebuild(check: str, keep: str) -> None:
    """SQLite cannot alter a check constraint, so move the rows to a new table."""
    op.create_table(
        _TEMP,
        sa.Column(
            "role",
            sa.Enum(
                "generation",
                "image_generation",
                name="modelrole",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.CheckConstraint(
            check, name=op.f("ck_selected_models_provider_connection")
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
            INSERT INTO {_TEMP} (role, provider, connection_id, name, updated_at)
            SELECT role, provider, connection_id, name, updated_at
            FROM selected_models
            WHERE {keep}
            """
        )
    )
    op.drop_table("selected_models")
    op.rename_table(_TEMP, "selected_models")


def upgrade() -> None:
    _rebuild(LOCAL_AND_REMOTE, keep="1")


def downgrade() -> None:
    # A local image selection cannot exist under the old rule; drop it rather
    # than fail, the same way 0004 dropped what it could not carry across.
    _rebuild(OLLAMA_AND_REMOTE, keep="provider <> 'sdcpp'")
