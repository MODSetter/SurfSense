"""Add LLMConfig table and user LLM preferences

Revision ID: 11
Revises: 10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "11"
down_revision: str | None = "10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add LiteLLMProvider enum, LLMConfig table and user LLM preferences."""

    # Create enum only if not exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'litellmprovider') THEN
                CREATE TYPE litellmprovider AS ENUM (
                    'OPENAI', 'ANTHROPIC', 'GROQ', 'COHERE', 'HUGGINGFACE',
                    'AZURE_OPENAI', 'GOOGLE', 'AWS_BEDROCK', 'OLLAMA', 'MISTRAL',
                    'TOGETHER_AI', 'REPLICATE', 'PALM', 'VERTEX_AI', 'ANYSCALE',
                    'PERPLEXITY', 'DEEPINFRA', 'AI21', 'NLPCLOUD', 'ALEPH_ALPHA',
                    'PETALS', 'CUSTOM'
                );
            END IF;
        END$$;
    """
    )

    # Create llm_configs table only if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'llm_configs'
            ) THEN
                CREATE TABLE llm_configs (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    name VARCHAR(100) NOT NULL,
                    provider litellmprovider NOT NULL,
                    custom_provider VARCHAR(100),
                    model_name VARCHAR(100) NOT NULL,
                    api_key TEXT NOT NULL,
                    api_base VARCHAR(500),
                    litellm_params JSONB,
                    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
                );
            END IF;
        END$$;
    """
    )

    # Create indexes if they don't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'llm_configs' AND indexname = 'ix_llm_configs_id'
            ) THEN
                CREATE INDEX ix_llm_configs_id ON llm_configs(id);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'llm_configs' AND indexname = 'ix_llm_configs_created_at'
            ) THEN
                CREATE INDEX ix_llm_configs_created_at ON llm_configs(created_at);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'llm_configs' AND indexname = 'ix_llm_configs_name'
            ) THEN
                CREATE INDEX ix_llm_configs_name ON llm_configs(name);
            END IF;
        END$$;
    """
    )

    # Safely add columns to user table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("user")]

    with op.batch_alter_table("user") as batch_op:
        if "long_context_llm_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("long_context_llm_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                op.f("fk_user_long_context_llm_id_llm_configs"),
                "llm_configs",
                ["long_context_llm_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if "fast_llm_id" not in existing_columns:
            batch_op.add_column(sa.Column("fast_llm_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                op.f("fk_user_fast_llm_id_llm_configs"),
                "llm_configs",
                ["fast_llm_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if "strategic_llm_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("strategic_llm_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                op.f("fk_user_strategic_llm_id_llm_configs"),
                "llm_configs",
                ["strategic_llm_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    """Downgrade schema - remove LLMConfig table and user LLM preferences."""

    # Drop foreign key constraints
    op.drop_constraint(
        op.f("fk_user_strategic_llm_id_llm_configs"), "user", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_user_fast_llm_id_llm_configs"), "user", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_user_long_context_llm_id_llm_configs"), "user", type_="foreignkey"
    )

    # Drop LLM preference columns from user table
    op.drop_column("user", "strategic_llm_id")
    op.drop_column("user", "fast_llm_id")
    op.drop_column("user", "long_context_llm_id")

    # Drop indexes and table
    op.drop_index(op.f("ix_llm_configs_name"), table_name="llm_configs")
    op.drop_index(op.f("ix_llm_configs_created_at"), table_name="llm_configs")
    op.drop_index(op.f("ix_llm_configs_id"), table_name="llm_configs")
    op.drop_table("llm_configs")

    # Drop LiteLLMProvider enum
    op.execute("DROP TYPE IF EXISTS litellmprovider")
