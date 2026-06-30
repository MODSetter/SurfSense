"""harden refresh token schema

Revision ID: 168
Revises: 167
"""

from collections.abc import Sequence

from alembic import op

revision: str = "168"
down_revision: str | None = "167"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS "
        "revoked_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS "
        "absolute_expiry TIMESTAMP WITH TIME ZONE"
    )

    bind = op.get_bind()
    is_revoked_exists = bind.execute(
        sa.text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'refresh_tokens'
              AND column_name = 'is_revoked'
        )
        """
        )
    ).scalar()

    if is_revoked_exists:
        op.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NOW()
            WHERE is_revoked = TRUE
              AND revoked_at IS NULL
            """
        )

    op.execute(
        "ALTER TABLE refresh_tokens ALTER COLUMN token_hash TYPE VARCHAR(64)"
    )
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS is_revoked")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS "
        "is_revoked BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'refresh_tokens'
                  AND column_name = 'revoked_at'
            ) THEN
                UPDATE refresh_tokens SET is_revoked = TRUE WHERE revoked_at IS NOT NULL;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN is_revoked DROP DEFAULT")
    op.execute(
        "ALTER TABLE refresh_tokens ALTER COLUMN token_hash TYPE VARCHAR(256)"
    )
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS absolute_expiry")
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS revoked_at")
