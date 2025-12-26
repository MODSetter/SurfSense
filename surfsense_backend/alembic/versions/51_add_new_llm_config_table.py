"""Add NewLLMConfig table for configurable LLM + prompt settings

Revision ID: 51
Revises: 50
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "51"
down_revision: str | None = "50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add the new_llm_configs table that combines LLM model settings with prompt configuration.

    This table includes:
    - LLM model configuration (provider, model_name, api_key, etc.)
    - Configurable system instructions
    - Citation toggle
    """
    # Create new_llm_configs table only if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'new_llm_configs'
            ) THEN
                CREATE TABLE new_llm_configs (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    
                    -- Basic info
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(500),
                    
                    -- LLM Model Configuration (same as llm_configs, excluding language)
                    provider litellmprovider NOT NULL,
                    custom_provider VARCHAR(100),
                    model_name VARCHAR(100) NOT NULL,
                    api_key TEXT NOT NULL,
                    api_base VARCHAR(500),
                    litellm_params JSONB DEFAULT '{}',
                    
                    -- Prompt Configuration
                    system_instructions TEXT NOT NULL DEFAULT '',
                    use_default_system_instructions BOOLEAN NOT NULL DEFAULT TRUE,
                    citations_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    
                    -- Default flag
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    
                    -- Foreign key to search space
                    search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE
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
                WHERE tablename = 'new_llm_configs' AND indexname = 'ix_new_llm_configs_id'
            ) THEN
                CREATE INDEX ix_new_llm_configs_id ON new_llm_configs(id);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'new_llm_configs' AND indexname = 'ix_new_llm_configs_created_at'
            ) THEN
                CREATE INDEX ix_new_llm_configs_created_at ON new_llm_configs(created_at);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'new_llm_configs' AND indexname = 'ix_new_llm_configs_name'
            ) THEN
                CREATE INDEX ix_new_llm_configs_name ON new_llm_configs(name);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'new_llm_configs' AND indexname = 'ix_new_llm_configs_search_space_id'
            ) THEN
                CREATE INDEX ix_new_llm_configs_search_space_id ON new_llm_configs(search_space_id);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Remove the new_llm_configs table."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_new_llm_configs_search_space_id")
    op.execute("DROP INDEX IF EXISTS ix_new_llm_configs_name")
    op.execute("DROP INDEX IF EXISTS ix_new_llm_configs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_new_llm_configs_id")

    # Drop table
    op.execute("DROP TABLE IF EXISTS new_llm_configs")
