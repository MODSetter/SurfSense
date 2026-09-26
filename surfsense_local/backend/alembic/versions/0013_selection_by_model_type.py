"""Key a selection by the model's type instead of a role.

`generation` and `image_generation` were a second word for `text_gen` and
`image_gen`, one to one, so the rows are renamed in place. The three types no
feature reads yet get a slot too; downgrading drops a selection in one of them,
because the old schema has no key to hold it.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")
_TEMP = "_selected_models_0013"

PROVIDER_CONNECTION = (
    "(provider IN ('llamacpp', 'sdcpp') AND connection_id IS NULL) OR "
    "(provider = 'openai_compatible' AND connection_id IS NOT NULL)"
)
# A local runtime serves one type: llama.cpp answers text, sd-server draws.
LOCAL_RUNTIME_TYPE = (
    "(provider <> 'llamacpp' OR model_type = 'text_gen') AND "
    "(provider <> 'sdcpp' OR model_type = 'image_gen')"
)
MODEL_TYPES = ("text_gen", "image_gen", "image_edit", "video_gen", "audio_gen")
ROLES = ("generation", "image_generation")
ROLE_TO_TYPE = {"generation": "text_gen", "image_generation": "image_gen"}


def _rebuild(
    key: str,
    values: Sequence[str],
    enum_name: str,
    select_key: str,
    keep: str,
    extra_checks: Sequence[sa.CheckConstraint] = (),
) -> None:
    """SQLite cannot rename a primary key column, so move the rows to a new table."""
    op.create_table(
        _TEMP,
        sa.Column(
            key,
            sa.Enum(*values, name=enum_name, native_enum=False, create_constraint=True),
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
                "flagship", "small", name="line", native_enum=False, create_constraint=True
            ),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.CheckConstraint(
            PROVIDER_CONNECTION, name=op.f("ck_selected_models_provider_connection")
        ),
        *extra_checks,
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["provider_connections.id"],
            name=op.f("fk_selected_models_connection_id_provider_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(key, name=op.f("pk_selected_models")),
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO {_TEMP}
                ({key}, provider, connection_id, name, params_b, vendor, line, updated_at)
            SELECT {select_key}, provider, connection_id, name, params_b, vendor, line, updated_at
            FROM selected_models
            WHERE {keep}
            """
        )
    )
    op.drop_table("selected_models")
    op.rename_table(_TEMP, "selected_models")


def _case(column: str, mapping: dict[str, str]) -> str:
    whens = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE {column} {whens} END"


def upgrade() -> None:
    _rebuild(
        "model_type",
        MODEL_TYPES,
        "modeltype",
        _case("role", ROLE_TO_TYPE),
        keep="1 = 1",
        extra_checks=(
            sa.CheckConstraint(
                LOCAL_RUNTIME_TYPE, name=op.f("ck_selected_models_local_runtime_type")
            ),
        ),
    )


def downgrade() -> None:
    back = {new: old for old, new in ROLE_TO_TYPE.items()}
    listed = ", ".join(f"'{value}'" for value in back)
    _rebuild(
        "role",
        ROLES,
        "modelrole",
        _case("model_type", back),
        keep=f"model_type IN ({listed})",
    )
