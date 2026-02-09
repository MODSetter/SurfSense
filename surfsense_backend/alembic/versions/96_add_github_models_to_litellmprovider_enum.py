"""Add GITHUB_MODELS to LiteLLMProvider enum

Revision ID: 96
Revises: 95
"""

from collections.abc import Sequence

from alembic import op

revision: str = "96"
down_revision: str | None = "95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'GITHUB_MODELS'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'GITHUB_MODELS';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    pass
