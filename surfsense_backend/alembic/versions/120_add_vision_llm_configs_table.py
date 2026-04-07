"""Add vision LLM configs table and rename preference column

Revision ID: 120
Revises: 119

Changes:
1. Create visionprovider enum type
2. Create vision_llm_configs table
3. Rename vision_llm_id -> vision_llm_config_id on searchspaces
4. Add vision config permissions to existing system roles
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, UUID

from alembic import op

revision: str = "120"
down_revision: str | None = "119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VISION_PROVIDER_VALUES = (
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
)


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Create visionprovider enum
    connection.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'visionprovider') THEN
                    CREATE TYPE visionprovider AS ENUM (
                        'OPENAI', 'ANTHROPIC', 'GOOGLE', 'AZURE_OPENAI', 'VERTEX_AI',
                        'BEDROCK', 'XAI', 'OPENROUTER', 'OLLAMA', 'GROQ',
                        'TOGETHER_AI', 'FIREWORKS_AI', 'DEEPSEEK', 'MISTRAL', 'CUSTOM'
                    );
                END IF;
            END
            $$;
            """
        )
    )

    # 2. Create vision_llm_configs table
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'vision_llm_configs')"
        )
    )
    if not result.scalar():
        op.create_table(
            "vision_llm_configs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column(
                "provider",
                PG_ENUM(*VISION_PROVIDER_VALUES, name="visionprovider", create_type=False),
                nullable=False,
            ),
            sa.Column("custom_provider", sa.String(100), nullable=True),
            sa.Column("model_name", sa.String(100), nullable=False),
            sa.Column("api_key", sa.String(), nullable=False),
            sa.Column("api_base", sa.String(500), nullable=True),
            sa.Column("api_version", sa.String(50), nullable=True),
            sa.Column("litellm_params", sa.JSON(), nullable=True),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], ondelete="CASCADE"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_vision_llm_configs_name "
            "ON vision_llm_configs (name)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_vision_llm_configs_search_space_id "
            "ON vision_llm_configs (search_space_id)"
        )

    # 3. Rename vision_llm_id -> vision_llm_config_id on searchspaces
    existing_columns = [
        col["name"] for col in sa.inspect(connection).get_columns("searchspaces")
    ]
    if "vision_llm_id" in existing_columns and "vision_llm_config_id" not in existing_columns:
        op.alter_column("searchspaces", "vision_llm_id", new_column_name="vision_llm_config_id")
    elif "vision_llm_config_id" not in existing_columns:
        op.add_column(
            "searchspaces",
            sa.Column("vision_llm_config_id", sa.Integer(), nullable=True, server_default="0"),
        )

    # 4. Add vision config permissions to existing system roles
    connection.execute(
        sa.text(
            """
            UPDATE search_space_roles
            SET permissions = array_cat(
                permissions,
                ARRAY['vision_configs:create', 'vision_configs:read']
            )
            WHERE is_system_role = true
              AND name = 'Editor'
              AND NOT ('vision_configs:create' = ANY(permissions))
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE search_space_roles
            SET permissions = array_cat(
                permissions,
                ARRAY['vision_configs:read']
            )
            WHERE is_system_role = true
              AND name = 'Viewer'
              AND NOT ('vision_configs:read' = ANY(permissions))
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()

    # Remove permissions
    connection.execute(
        sa.text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(
                array_remove(
                    array_remove(permissions, 'vision_configs:create'),
                    'vision_configs:read'
                ),
                'vision_configs:delete'
            )
            WHERE is_system_role = true
            """
        )
    )

    # Rename column back
    existing_columns = [
        col["name"] for col in sa.inspect(connection).get_columns("searchspaces")
    ]
    if "vision_llm_config_id" in existing_columns:
        op.alter_column("searchspaces", "vision_llm_config_id", new_column_name="vision_llm_id")

    # Drop table and enum
    op.execute("DROP INDEX IF EXISTS ix_vision_llm_configs_search_space_id")
    op.execute("DROP INDEX IF EXISTS ix_vision_llm_configs_name")
    op.execute("DROP TABLE IF EXISTS vision_llm_configs")
    op.execute("DROP TYPE IF EXISTS visionprovider")
