"""Let the bundled audio.cpp server hold the speech recognition slot.

Nemotron 3.5 ASR runs on a second audio.cpp server, so `audiocpp` serves
`audio_gen` and `speech_to_text`, and the type CHECK lists six slots. SQLite
cannot alter a check constraint, so the table is rebuilt; unlike 0018's
rebuild, this one carries 0019's `settings`, which holds the voices a user
added. Downgrading drops a speech recognition selection, which the old checks
cannot hold.

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("(CURRENT_TIMESTAMP)")
_TEMP = "_selected_models_0030"
FIVE_SLOTS = ("text_gen", "image_gen", "image_edit", "video_gen", "audio_gen")
SIX_SLOTS = (*FIVE_SLOTS, "speech_to_text")
COLUMNS = (
    "model_type, provider, connection_id, name, params_b, vendor, line, "
    "settings, updated_at"
)

_PROVIDER_CONNECTION = (
    "(provider IN ('llamacpp', 'sdcpp', 'audiocpp') AND connection_id IS NULL) OR "
    "(provider = 'openai_compatible' AND connection_id IS NOT NULL)"
)
_TEXT_AND_IMAGES = (
    "(provider <> 'llamacpp' OR model_type = 'text_gen') AND "
    "(provider <> 'sdcpp' OR model_type IN ('image_gen', 'image_edit', 'video_gen'))"
)
SPEAKS_AND_HEARS = (
    _PROVIDER_CONNECTION,
    f"{_TEXT_AND_IMAGES} AND "
    "(provider <> 'audiocpp' OR model_type IN ('audio_gen', 'speech_to_text'))",
)
SPEAKS = (
    _PROVIDER_CONNECTION,
    f"{_TEXT_AND_IMAGES} AND (provider <> 'audiocpp' OR model_type = 'audio_gen')",
)


def _rebuild(model_types: tuple[str, ...], checks: tuple[str, str], keep: str) -> None:
    provider_connection, local_runtime_type = checks
    op.create_table(
        _TEMP,
        sa.Column(
            "model_type",
            sa.Enum(
                *model_types,
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
        sa.Column("settings", sa.JSON(), nullable=True),
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
    _rebuild(SIX_SLOTS, SPEAKS_AND_HEARS, keep="1 = 1")


def downgrade() -> None:
    _rebuild(FIVE_SLOTS, SPEAKS, keep="model_type <> 'speech_to_text'")
