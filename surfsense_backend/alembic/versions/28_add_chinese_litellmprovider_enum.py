"""Add Chinese LLM providers to LiteLLMProvider enum

Revision ID: 28
Revises: 27
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "28"
down_revision: str | None = "27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add Chinese LLM providers to LiteLLMProvider enum.

    Adds support for:
    - DEEPSEEK: DeepSeek AI models
    - ALIBABA_QWEN: Alibaba Qwen models
    - MOONSHOT: Moonshot AI models
    - ZHIPU: Zhipu AI models
    """

    # Add DEEPSEEK to the enum if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'DEEPSEEK'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'DEEPSEEK';
            END IF;
        END$$;
        """
    )

    # Add ALIBABA_QWEN to the enum if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'ALIBABA_QWEN'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'ALIBABA_QWEN';
            END IF;
        END$$;
        """
    )

    # Add MOONSHOT to the enum if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'MOONSHOT'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'MOONSHOT';
            END IF;
        END$$;
        """
    )

    # Add ZHIPU to the enum if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'ZHIPU'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'ZHIPU';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """
    Remove Chinese LLM providers from LiteLLMProvider enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type and updating all dependent objects.
    For safety, this downgrade is a no-op.

    """
    # PostgreSQL doesn't support removing enum values directly
    # This would require a complex migration recreating the enum
    # PostgreSQL 不支持直接删除枚举值
    # 这需要复杂的迁移来重建枚举
    pass
