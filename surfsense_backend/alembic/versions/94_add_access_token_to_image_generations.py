"""Add access_token column to image_generations

Revision ID: 94
Revises: 93

Adds an indexed access_token column to the image_generations table.
This token is stored per-record so that image serving URLs survive
SECRET_KEY rotation.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94"
down_revision: str | None = "93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add access_token column (nullable so existing rows are unaffected)
    # Guard: skip entirely if image_generations table doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'image_generations'
            ) THEN
                -- Add column if not exists
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'image_generations' AND column_name = 'access_token'
                ) THEN
                    ALTER TABLE image_generations
                    ADD COLUMN access_token VARCHAR(64);
                END IF;

                -- Create index if not exists
                CREATE INDEX IF NOT EXISTS ix_image_generations_access_token
                ON image_generations (access_token);
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_image_generations_access_token")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'image_generations' AND column_name = 'access_token'
            ) THEN
                ALTER TABLE image_generations DROP COLUMN access_token;
            END IF;
        END$$;
        """
    )
