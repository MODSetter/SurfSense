"""Add OPENROUTER to LiteLLMProvider enum

Revision ID: 20
Revises: 19
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20"
down_revision: str | None = "19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add OPENROUTER to LiteLLMProvider enum."""

    # Add OPENROUTER to the enum if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'OPENROUTER'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'OPENROUTER';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Remove OPENROUTER from LiteLLMProvider enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type and updating all dependent objects.
    For safety, this downgrade is a no-op.
    """
    # PostgreSQL doesn't support removing enum values directly
    # This would require a complex migration recreating the enum
    pass
