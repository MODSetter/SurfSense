"""Update LiteLLMProvider enum with comprehensive provider support

This migration adds support for all major LiteLLM providers including:
- Fast inference platforms (XAI, Cerebras, SambaNova, Fireworks AI)
- Cloud platforms (Cloudflare, Databricks)
- Renames AWS_BEDROCK to BEDROCK for consistency
- Adds CUSTOM for custom OpenAI-compatible endpoints

Revision ID: 35
Revises: 34
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "35"
down_revision: str | None = "34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add new LLM providers to LiteLLMProvider enum and migrate existing data.

    New providers added:
    - XAI: xAI's Grok models
    - FIREWORKS_AI: Fireworks AI platform
    - CEREBRAS: Cerebras inference platform (fastest)
    - SAMBANOVA: SambaNova inference platform
    - CLOUDFLARE: Cloudflare Workers AI
    - DATABRICKS: Databricks Model Serving
    - BEDROCK: AWS Bedrock (replaces AWS_BEDROCK)
    - CUSTOM: Custom OpenAI-compatible endpoints
    """

    # Add XAI (xAI Grok models)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'XAI'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'XAI';
            END IF;
        END$$;
        """
    )

    # Add FIREWORKS_AI
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'FIREWORKS_AI'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'FIREWORKS_AI';
            END IF;
        END$$;
        """
    )

    # Add CEREBRAS (fastest inference platform)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'CEREBRAS'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'CEREBRAS';
            END IF;
        END$$;
        """
    )

    # Add SAMBANOVA
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'SAMBANOVA'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'SAMBANOVA';
            END IF;
        END$$;
        """
    )

    # Add CLOUDFLARE (Cloudflare Workers AI)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'CLOUDFLARE'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'CLOUDFLARE';
            END IF;
        END$$;
        """
    )

    # Add DATABRICKS
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'DATABRICKS'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'DATABRICKS';
            END IF;
        END$$;
        """
    )

    # Add BEDROCK (new standardized name)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'BEDROCK'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'BEDROCK';
            END IF;
        END$$;
        """
    )

    # Add CUSTOM for custom OpenAI-compatible endpoints
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'CUSTOM'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'CUSTOM';
            END IF;
        END$$;
        """
    )

    # Note: Both AWS_BEDROCK and BEDROCK will coexist in the enum for backward compatibility.
    # - New configurations will use BEDROCK (via the frontend)
    # - Existing AWS_BEDROCK configurations will continue to work
    # - The backend service handles both values correctly
    #
    # Legacy enum values (PALM, NLPCLOUD, ALEPH_ALPHA, PETALS, etc.) also remain in the enum.
    # PostgreSQL doesn't support removing enum values without recreating the entire type.
    #
    # Data migration from AWS_BEDROCK -> BEDROCK is NOT performed because:
    # 1. PostgreSQL doesn't allow using new enum values in the same transaction
    # 2. Both values work correctly with the backend service
    # 3. Users can manually update old configs if desired (not required)


def downgrade() -> None:
    """
    Downgrade migration.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the entire enum type and updating all dependent objects.
    For safety and data preservation, this downgrade is a no-op.

    If you need to downgrade, you should:
    1. Ensure no llm_configs are using the new providers
    2. Manually remove enum values (requires enum recreation - complex operation)

    This is not automated to prevent accidental data loss.
    New enum values (XAI, FIREWORKS_AI, CEREBRAS, BEDROCK, etc.) will remain
    in the database but won't be selectable in the application after downgrade.
    """
    # PostgreSQL doesn't support removing enum values directly
    # This is a no-op for safety
    pass
