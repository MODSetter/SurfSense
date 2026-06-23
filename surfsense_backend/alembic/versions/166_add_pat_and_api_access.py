"""Add personal access tokens and search-space API access gate.

Revision ID: 166
Revises: 165
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "166"
down_revision: str | None = "165"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS personal_access_tokens (
            id SERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) NOT NULL,
            token_prefix VARCHAR(16) NOT NULL,
            label VARCHAR NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE,
            last_used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL
        );
        """
    )

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_personal_access_tokens_token_hash "
        "ON personal_access_tokens (token_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_personal_access_tokens_user_id "
        "ON personal_access_tokens (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_personal_access_tokens_id "
        "ON personal_access_tokens (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_personal_access_tokens_created_at "
        "ON personal_access_tokens (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_personal_access_tokens_expires_at "
        "ON personal_access_tokens (expires_at)"
    )

    bind = op.get_bind()
    api_access_column_exists = bind.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'searchspaces'
              AND column_name = 'api_access_enabled'
        )
        """
        )
    ).scalar()

    op.execute(
        "ALTER TABLE searchspaces ADD COLUMN IF NOT EXISTS "
        "api_access_enabled BOOLEAN NOT NULL DEFAULT false"
    )

    if not api_access_column_exists:
        op.execute("UPDATE searchspaces SET api_access_enabled = true")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE searchspaces DROP COLUMN IF EXISTS api_access_enabled"
    )
    op.execute("DROP TABLE IF EXISTS personal_access_tokens")
