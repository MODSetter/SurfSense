"""Add Chinese LLM providers to LiteLLMProvider enum
添加国产 LLM 提供商到 LiteLLMProvider 枚举

Revision ID: 26
Revises: 25
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26"
down_revision: str | None = "25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add Chinese LLM providers to LiteLLMProvider enum.
    添加国产 LLM 提供商到 LiteLLMProvider 枚举。
    
    Adds support for:
    - DEEPSEEK: DeepSeek AI models
    - ALIBABA_QWEN: Alibaba Qwen (通义千问) models
    - MOONSHOT: Moonshot AI (月之暗面 Kimi) models
    - ZHIPU: Zhipu AI (智谱 GLM) models
    """
    
    # Add DEEPSEEK to the enum if it doesn't already exist
    # 如果不存在则添加 DEEPSEEK 到枚举
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
    # 如果不存在则添加 ALIBABA_QWEN 到枚举
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
    # 如果不存在则添加 MOONSHOT 到枚举
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
    # 如果不存在则添加 ZHIPU 到枚举
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
    从 LiteLLMProvider 枚举中移除国产 LLM 提供商。
    
    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type and updating all dependent objects.
    For safety, this downgrade is a no-op.
    
    注意：PostgreSQL 不支持直接删除枚举值。
    这需要重建枚举类型并更新所有依赖对象。
    为了安全起见，此降级操作为空操作。
    """
    # PostgreSQL doesn't support removing enum values directly
    # This would require a complex migration recreating the enum
    # PostgreSQL 不支持直接删除枚举值
    # 这需要复杂的迁移来重建枚举
    pass

