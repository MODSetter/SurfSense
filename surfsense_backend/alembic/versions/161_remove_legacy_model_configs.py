"""remove legacy model config tables

Revision ID: 161
Revises: 160
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeEngine

from alembic import op

revision: str = "161"
down_revision: str | None = "160"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


litellm_provider = postgresql.ENUM(
    "OPENAI",
    "ANTHROPIC",
    "GOOGLE",
    "AZURE_OPENAI",
    "BEDROCK",
    "VERTEX_AI",
    "GROQ",
    "COHERE",
    "MISTRAL",
    "DEEPSEEK",
    "XAI",
    "OPENROUTER",
    "TOGETHER_AI",
    "FIREWORKS_AI",
    "REPLICATE",
    "PERPLEXITY",
    "OLLAMA",
    "ALIBABA_QWEN",
    "MOONSHOT",
    "ZHIPU",
    "ANYSCALE",
    "DEEPINFRA",
    "CEREBRAS",
    "SAMBANOVA",
    "AI21",
    "CLOUDFLARE",
    "DATABRICKS",
    "COMETAPI",
    "HUGGINGFACE",
    "GITHUB_MODELS",
    "MINIMAX",
    "CUSTOM",
    name="litellmprovider",
    create_type=False,
)
image_gen_provider = postgresql.ENUM(
    "OPENAI",
    "AZURE_OPENAI",
    "GOOGLE",
    "VERTEX_AI",
    "BEDROCK",
    "RECRAFT",
    "OPENROUTER",
    "XINFERENCE",
    "NSCALE",
    name="imagegenprovider",
    create_type=False,
)
vision_provider = postgresql.ENUM(
    "OPENAI",
    "ANTHROPIC",
    "GOOGLE",
    "AZURE_OPENAI",
    "VERTEX_AI",
    "BEDROCK",
    "XAI",
    "OPENROUTER",
    "OLLAMA",
    "GROQ",
    "TOGETHER_AI",
    "FIREWORKS_AI",
    "DEEPSEEK",
    "MISTRAL",
    "CUSTOM",
    name="visionprovider",
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


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _rename_column_if_exists(
    table_name: str,
    old_column_name: str,
    new_column_name: str,
    *,
    existing_type: TypeEngine,
    existing_nullable: bool = True,
) -> None:
    if _column_exists(table_name, old_column_name) and not _column_exists(
        table_name, new_column_name
    ):
        op.alter_column(
            table_name,
            old_column_name,
            new_column_name=new_column_name,
            existing_type=existing_type,
            existing_nullable=existing_nullable,
        )


def upgrade() -> None:
    for table_name in (
        "new_llm_configs",
        "vision_llm_configs",
        "image_generation_configs",
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)

    _drop_column_if_exists("searchspaces", "agent_llm_id")
    _drop_column_if_exists("searchspaces", "image_generation_config_id")
    _drop_column_if_exists("searchspaces", "vision_llm_config_id")

    _rename_column_if_exists(
        "image_generations",
        "image_generation_config_id",
        "image_gen_model_id",
        existing_type=sa.Integer(),
    )

    op.execute("DROP TYPE IF EXISTS litellmprovider")
    op.execute("DROP TYPE IF EXISTS imagegenprovider")
    op.execute("DROP TYPE IF EXISTS visionprovider")


def downgrade() -> None:
    bind = op.get_bind()
    litellm_provider.create(bind, checkfirst=True)
    image_gen_provider.create(bind, checkfirst=True)
    vision_provider.create(bind, checkfirst=True)

    _rename_column_if_exists(
        "image_generations",
        "image_gen_model_id",
        "image_generation_config_id",
        existing_type=sa.Integer(),
    )

    if _table_exists("searchspaces"):
        if not _column_exists("searchspaces", "agent_llm_id"):
            op.add_column(
                "searchspaces",
                sa.Column("agent_llm_id", sa.Integer(), nullable=True),
            )
        if not _column_exists("searchspaces", "image_generation_config_id"):
            op.add_column(
                "searchspaces",
                sa.Column("image_generation_config_id", sa.Integer(), nullable=True),
            )
        if not _column_exists("searchspaces", "vision_llm_config_id"):
            op.add_column(
                "searchspaces",
                sa.Column("vision_llm_config_id", sa.Integer(), nullable=True),
            )

    if not _table_exists("image_generation_configs"):
        op.create_table(
            "image_generation_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("provider", image_gen_provider, nullable=False),
            sa.Column("custom_provider", sa.String(length=100), nullable=True),
            sa.Column("model_name", sa.String(length=100), nullable=False),
            sa.Column("api_key", sa.String(), nullable=False),
            sa.Column("api_base", sa.String(length=500), nullable=True),
            sa.Column("api_version", sa.String(length=50), nullable=True),
            sa.Column("litellm_params", sa.JSON(), nullable=True),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_image_generation_configs_name"),
            "image_generation_configs",
            ["name"],
            unique=False,
        )

    if not _table_exists("vision_llm_configs"):
        op.create_table(
            "vision_llm_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("provider", vision_provider, nullable=False),
            sa.Column("custom_provider", sa.String(length=100), nullable=True),
            sa.Column("model_name", sa.String(length=100), nullable=False),
            sa.Column("api_key", sa.String(), nullable=False),
            sa.Column("api_base", sa.String(length=500), nullable=True),
            sa.Column("api_version", sa.String(length=50), nullable=True),
            sa.Column("litellm_params", sa.JSON(), nullable=True),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_vision_llm_configs_name"),
            "vision_llm_configs",
            ["name"],
            unique=False,
        )

    if not _table_exists("new_llm_configs"):
        op.create_table(
            "new_llm_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("provider", litellm_provider, nullable=False),
            sa.Column("custom_provider", sa.String(length=100), nullable=True),
            sa.Column("model_name", sa.String(length=100), nullable=False),
            sa.Column("api_key", sa.String(), nullable=False),
            sa.Column("api_base", sa.String(length=500), nullable=True),
            sa.Column("litellm_params", sa.JSON(), nullable=True),
            sa.Column("system_instructions", sa.Text(), nullable=False),
            sa.Column("use_default_system_instructions", sa.Boolean(), nullable=False),
            sa.Column("citations_enabled", sa.Boolean(), nullable=False),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_new_llm_configs_name"),
            "new_llm_configs",
            ["name"],
            unique=False,
        )
