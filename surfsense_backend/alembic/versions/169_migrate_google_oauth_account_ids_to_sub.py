"""migrate Google OAuth account IDs to sub

Revision ID: 169
Revises: 168
"""

from collections.abc import Sequence

from alembic import op

revision: str = "169"
down_revision: str | None = "168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE oauth_account AS legacy
        SET account_id = regexp_replace(legacy.account_id, '^people/', '')
        WHERE legacy.oauth_name = 'google'
          AND legacy.account_id LIKE 'people/%'
          AND NOT EXISTS (
            SELECT 1
            FROM oauth_account AS canonical
            WHERE canonical.oauth_name = 'google'
              AND canonical.account_id = regexp_replace(legacy.account_id, '^people/', '')
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE oauth_account AS canonical
        SET account_id = 'people/' || canonical.account_id
        WHERE canonical.oauth_name = 'google'
          AND canonical.account_id NOT LIKE 'people/%'
          AND NOT EXISTS (
            SELECT 1
            FROM oauth_account AS legacy
            WHERE legacy.oauth_name = 'google'
              AND legacy.account_id = 'people/' || canonical.account_id
          )
        """
    )
