"""Migrate data from old llm_configs to new_llm_configs and cleanup

Revision ID: 53
Revises: 52
Create Date: 2024-12-22

This migration:
1. Migrates data from old llm_configs table to new_llm_configs (preserving user configs)
2. Updates searchspaces to point to migrated configs
3. Drops the old llm_configs table (no longer used)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "53"
down_revision = "52"
branch_labels = None
depends_on = None


def upgrade():
    # STEP 1: Migrate data from old llm_configs to new_llm_configs
    # This preserves any user-created configurations
    op.execute(
        """
        DO $$
        BEGIN
            -- Only migrate if both tables exist
            IF EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'llm_configs'
            ) AND EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'new_llm_configs'
            ) THEN
                -- Insert old configs into new table (skipping duplicates by name+search_space_id)
                INSERT INTO new_llm_configs (
                    name,
                    description,
                    provider,
                    custom_provider,
                    model_name,
                    api_key,
                    api_base,
                    litellm_params,
                    system_instructions,
                    use_default_system_instructions,
                    citations_enabled,
                    search_space_id,
                    created_at
                )
                SELECT 
                    lc.name,
                    NULL as description,  -- Old table didn't have description
                    lc.provider,
                    lc.custom_provider,
                    lc.model_name,
                    lc.api_key,
                    lc.api_base,
                    COALESCE(lc.litellm_params::json, '{}'::json),
                    '' as system_instructions,  -- Use defaults
                    TRUE as use_default_system_instructions,
                    TRUE as citations_enabled,
                    lc.search_space_id,
                    COALESCE(lc.created_at, NOW())
                FROM llm_configs lc
                WHERE lc.search_space_id IS NOT NULL
                AND NOT EXISTS (
                    -- Skip if a config with same name already exists in new_llm_configs for this search space
                    SELECT 1 FROM new_llm_configs nlc 
                    WHERE nlc.name = lc.name 
                    AND nlc.search_space_id = lc.search_space_id
                );
                
                -- Log how many configs were migrated
                RAISE NOTICE 'Migrated % configs from llm_configs to new_llm_configs', 
                    (SELECT COUNT(*) FROM llm_configs WHERE search_space_id IS NOT NULL);
            END IF;
        END$$;
        """
    )

    # STEP 2: Update searchspaces to point to new_llm_configs for their agent LLM
    # If a search space had an agent_llm_id pointing to old llm_configs,
    # try to find the corresponding config in new_llm_configs
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'llm_configs'
            ) THEN
                -- Update agent_llm_id to point to migrated config in new_llm_configs
                UPDATE searchspaces ss
                SET agent_llm_id = (
                    SELECT nlc.id 
                    FROM new_llm_configs nlc
                    JOIN llm_configs lc ON lc.name = nlc.name AND lc.search_space_id = nlc.search_space_id
                    WHERE lc.id = ss.agent_llm_id
                    AND nlc.search_space_id = ss.id
                    LIMIT 1
                )
                WHERE ss.agent_llm_id IS NOT NULL
                AND ss.agent_llm_id > 0  -- Only positive IDs (not global configs)
                AND EXISTS (
                    SELECT 1 FROM llm_configs lc WHERE lc.id = ss.agent_llm_id
                );
                
                -- Update document_summary_llm_id similarly
                UPDATE searchspaces ss
                SET document_summary_llm_id = (
                    SELECT nlc.id 
                    FROM new_llm_configs nlc
                    JOIN llm_configs lc ON lc.name = nlc.name AND lc.search_space_id = nlc.search_space_id
                    WHERE lc.id = ss.document_summary_llm_id
                    AND nlc.search_space_id = ss.id
                    LIMIT 1
                )
                WHERE ss.document_summary_llm_id IS NOT NULL
                AND ss.document_summary_llm_id > 0  -- Only positive IDs (not global configs)
                AND EXISTS (
                    SELECT 1 FROM llm_configs lc WHERE lc.id = ss.document_summary_llm_id
                );
            END IF;
        END$$;
        """
    )

    # STEP 3: Drop the old llm_configs table (data has been migrated)
    op.execute("DROP TABLE IF EXISTS llm_configs CASCADE")


def downgrade():
    # Recreate the old llm_configs table
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
                    name VARCHAR(100) NOT NULL,
                    provider litellmprovider NOT NULL,
                    custom_provider VARCHAR(100),
                    model_name VARCHAR(100) NOT NULL,
                    api_key TEXT NOT NULL,
                    api_base VARCHAR(500),
                    language VARCHAR(50),
                    litellm_params JSONB DEFAULT '{}',
                    search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS ix_llm_configs_id ON llm_configs(id);
                CREATE INDEX IF NOT EXISTS ix_llm_configs_name ON llm_configs(name);
                CREATE INDEX IF NOT EXISTS ix_llm_configs_created_at ON llm_configs(created_at);
            END IF;
        END$$;
        """
    )

    # Migrate data back from new_llm_configs to llm_configs
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'new_llm_configs'
            ) THEN
                INSERT INTO llm_configs (
                    name,
                    provider,
                    custom_provider,
                    model_name,
                    api_key,
                    api_base,
                    language,
                    litellm_params,
                    search_space_id,
                    created_at
                )
                SELECT 
                    nlc.name,
                    nlc.provider,
                    nlc.custom_provider,
                    nlc.model_name,
                    nlc.api_key,
                    nlc.api_base,
                    'English' as language,  -- Default language
                    COALESCE(nlc.litellm_params::jsonb, '{}'::jsonb),
                    nlc.search_space_id,
                    nlc.created_at
                FROM new_llm_configs nlc
                WHERE nlc.search_space_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM llm_configs lc 
                    WHERE lc.name = nlc.name 
                    AND lc.search_space_id = nlc.search_space_id
                );
            END IF;
        END$$;
        """
    )
