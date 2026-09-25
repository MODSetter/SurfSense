"""Let the bundled sd-server hold the image editing and video slots.

FLUX.2 klein edits with the files it generates with, and sd.cpp runs video
models too, so `sdcpp` serves `image_gen`, `image_edit` and `video_gen`.
SQLite cannot alter a check constraint, so the table is rebuilt; downgrading
drops an sd-server editing or video selection, which the old checks cannot
hold.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")
_TEMP = "_selected_models_0017"
MODEL_TYPES = ("text_gen", "image_gen", "image_edit", "video_gen", "audio_gen")
COLUMNS = (
    "model_type, provider, connection_id, name, params_b, vendor, line, updated_at"
)

_PROVIDER_CONNECTION = (
    "(provider IN ('llamacpp', 'sdcpp', 'audiocpp') AND connection_id IS NULL) OR "
    "(provider = 'openai_compatible' AND connection_id IS NOT NULL)"
)
WITH_EDIT_AND_VIDEO = (
    _PROVIDER_CONNECTION,
    "(provider <> 'llamacpp' OR model_type = 'text_gen') AND "
    "(provider <> 'sdcpp' OR model_type IN ('image_gen', 'image_edit', 'video_gen')) AND "
    "(provider <> 'audiocpp' OR model_type = 'audio_gen')",
)
IMAGE_ONLY = (
    _PROVIDER_CONNECTION,
    "(provider <> 'llamacpp' OR model_type = 'text_gen') AND "
    "(provider <> 'sdcpp' OR model_type = 'image_gen') AND "
    "(provider <> 'audiocpp' OR model_type = 'audio_gen')",
)


def _rebuild(checks: tuple[str, str], keep: str) -> None:
    provider_connection, local_runtime_type = checks
    op.create_table(
        _TEMP,
        sa.Column(
            "model_type",
            sa.Enum(
                *MODEL_TYPES,
                name="modeltype",
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
            provider_connection, name=op.f("ck_selected_models_provider_connection")
        ),
        sa.CheckConstraint(
            local_runtime_type, name=op.f("ck_selected_models_local_runtime_type")
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["provider_connections.id"],
            name=op.f("fk_selected_models_connection_id_provider_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("model_type", name=op.f("pk_selected_models")),
    )
    op.execute(
        sa.text(
            f"INSERT INTO {_TEMP} ({COLUMNS}) "
            f"SELECT {COLUMNS} FROM selected_models WHERE {keep}"
        )
    )
    op.drop_table("selected_models")
    op.rename_table(_TEMP, "selected_models")


def upgrade() -> None:
    _rebuild(WITH_EDIT_AND_VIDEO, keep="1 = 1")


def downgrade() -> None:
    _rebuild(IMAGE_ONLY, keep="provider <> 'sdcpp' OR model_type = 'image_gen'")
