"""Add COMETAPI to LiteLLMProvider enum

Revision ID: 22
Revises: 21
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22"
down_revision: str | None = "21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add COMETAPI to LiteLLMProvider enum."""

    # Add COMETAPI to the enum if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = 'litellmprovider'::regtype
                AND enumlabel = 'COMETAPI'
            ) THEN
                ALTER TYPE litellmprovider ADD VALUE 'COMETAPI';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Remove COMETAPI from LiteLLMProvider enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type and updating all dependent objects.
    For safety, this downgrade is a no-op.
    """
    # PostgreSQL doesn't support removing enum values directly
    # This would require a complex migration recreating the enum
    pass
