"""Replace the Ollama runtime with llama.cpp.

The only migration in this phase that touches user data, and the only
irreversible step in the swap. Two things happen, both deliberate:

**A generation selection pointing at Ollama is cleared, not remapped.** Its
weights live in a blob format the app no longer manages, so there is no honest
file to point at. Left alone it would make `resolve_generation()` raise
`unknown provider` and chat would die with no explanation.

**An `ollama_pull` egress grant becomes `model_download` only.** That one
destination split into two on the same host, and the two are different
consents: `model_download` fetches a repo the user named, `model_search` sends
text they are typing. Carrying one grant across both would manufacture a
consent nobody gave, so `model_search` starts unset.

Revisions 0004 and 0009 mention Ollama and are applied history on every
installed machine. They are not touched here; this does the data work.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")
_TEMP = "_selected_models_0012"

LLAMACPP_AND_REMOTE = (
    "(provider IN ('llamacpp', 'sdcpp') AND connection_id IS NULL) OR "
    "(provider = 'openai_compatible' AND connection_id IS NOT NULL)"
)
OLLAMA_AND_REMOTE = (
    "(provider IN ('ollama', 'sdcpp') AND connection_id IS NULL) OR "
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
        sa.Column("params_b", sa.Float(), nullable=True),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column(
            "line",
            sa.Enum(
                "flagship",
                "small",
                name="line",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
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
            INSERT INTO {_TEMP}
                (role, provider, connection_id, name, params_b, vendor, line, updated_at)
            SELECT role, provider, connection_id, name, params_b, vendor, line, updated_at
            FROM selected_models
            WHERE {keep}
            """
        )
    )
    op.drop_table("selected_models")
    op.rename_table(_TEMP, "selected_models")


def upgrade() -> None:
    _rebuild(LLAMACPP_AND_REMOTE, keep="provider <> 'ollama'")
    op.execute(
        sa.text(
            "UPDATE egress_destinations SET destination = 'model_download' "
            "WHERE destination = 'ollama_pull'"
        )
    )


def downgrade() -> None:
    # A llamacpp selection cannot exist under the old rule, so drop it rather
    # than fail, the same way 0009 dropped what it could not carry across.
    _rebuild(OLLAMA_AND_REMOTE, keep="provider <> 'llamacpp'")
    op.execute(
        sa.text(
            "UPDATE egress_destinations SET destination = 'ollama_pull' "
            "WHERE destination = 'model_download'"
        )
    )
