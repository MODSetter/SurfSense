"""Add user_id to new_llm_configs and image_generation_configs

Revision ID: 96
Revises: 95
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "96"
down_revision: str | None = "95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add user_id column to new_llm_configs and image_generation_configs.

    Backfills existing rows with the search space owner's user_id.
    """
    # --- new_llm_configs ---
    # 1. Add nullable column first
    op.execute(
        """
        ALTER TABLE new_llm_configs
        ADD COLUMN IF NOT EXISTS user_id UUID;
        """
    )

    # 2. Backfill from search space owner
    op.execute(
        """
        UPDATE new_llm_configs nlc
        SET user_id = ss.user_id
        FROM searchspaces ss
        WHERE nlc.search_space_id = ss.id
          AND nlc.user_id IS NULL;
        """
    )

    # 3. Make NOT NULL
    op.execute(
        """
        ALTER TABLE new_llm_configs
        ALTER COLUMN user_id SET NOT NULL;
        """
    )

    # 4. Add FK constraint
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_new_llm_configs_user_id'
                  AND table_name = 'new_llm_configs'
            ) THEN
                ALTER TABLE new_llm_configs
                ADD CONSTRAINT fk_new_llm_configs_user_id
                FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE;
            END IF;
        END$$;
        """
    )

    # 5. Add index for user_id lookups
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_new_llm_configs_user_id
        ON new_llm_configs (user_id);
        """
    )

    # --- image_generation_configs ---
    # 1. Add nullable column first
    op.execute(
        """
        ALTER TABLE image_generation_configs
        ADD COLUMN IF NOT EXISTS user_id UUID;
        """
    )

    # 2. Backfill from search space owner
    op.execute(
        """
        UPDATE image_generation_configs igc
        SET user_id = ss.user_id
        FROM searchspaces ss
        WHERE igc.search_space_id = ss.id
          AND igc.user_id IS NULL;
        """
    )

    # 3. Make NOT NULL
    op.execute(
        """
        ALTER TABLE image_generation_configs
        ALTER COLUMN user_id SET NOT NULL;
        """
    )

    # 4. Add FK constraint
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_image_generation_configs_user_id'
                  AND table_name = 'image_generation_configs'
            ) THEN
                ALTER TABLE image_generation_configs
                ADD CONSTRAINT fk_image_generation_configs_user_id
                FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE;
            END IF;
        END$$;
        """
    )

    # 5. Add index for user_id lookups
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_image_generation_configs_user_id
        ON image_generation_configs (user_id);
        """
    )


def downgrade() -> None:
    """Remove user_id from new_llm_configs and image_generation_configs."""
    op.execute(
        """
        ALTER TABLE new_llm_configs DROP COLUMN IF EXISTS user_id;
        """
    )
    op.execute(
        """
        ALTER TABLE image_generation_configs DROP COLUMN IF EXISTS user_id;
        """
    )
