"""47_copy_created_at_to_updated_at

Revision ID: 47
Revises: 46
Create Date: 2025-12-12

Copies created_at values to updated_at for all documents where updated_at is NULL.
This ensures time-based filtering in retrievers works correctly for all documents.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "47"
down_revision: str | None = "46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Copy created_at to updated_at where updated_at is NULL."""
    # Set updated_at to created_at for all documents that don't have an updated_at value
    op.execute(
        """
        UPDATE documents
        SET updated_at = created_at
        WHERE updated_at IS NULL
          AND created_at IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema - Set updated_at back to NULL where it was copied from created_at."""
    # Note: This is a lossy downgrade - we cannot distinguish between documents
    # that had updated_at set by this migration vs. other sources.
    # For safety, we don't automatically revert these changes.
    pass
