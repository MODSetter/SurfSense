"""Migrate LLM configs to search spaces and add user preferences

Revision ID: 25
Revises: 24

Changes:
1. Migrate llm_configs from user association to search_space association
2. Create user_search_space_preferences table for per-user LLM preferences
3. Migrate existing user LLM preferences to user_search_space_preferences
4. Remove LLM preference columns from user table
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25"
down_revision: str | None = "24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Upgrade schema to support collaborative search spaces with per-user preferences.

    Migration steps:
    1. Add search_space_id to llm_configs
    2. Migrate existing llm_configs to first search space of their user
    3. Replace user_id with search_space_id in llm_configs
    4. Create user_search_space_preferences table
    5. Migrate user LLM preferences to user_search_space_preferences
    6. Remove LLM preference columns from user table
    """

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns
    llm_config_columns = [col["name"] for col in inspector.get_columns("llm_configs")]
    user_columns = [col["name"] for col in inspector.get_columns("user")]

    # ===== STEP 1: Add search_space_id to llm_configs =====
    if "search_space_id" not in llm_config_columns:
        op.add_column(
            "llm_configs",
            sa.Column("search_space_id", sa.Integer(), nullable=True),
        )

    # ===== STEP 2: Populate search_space_id with user's first search space =====
    # This ensures existing LLM configs are assigned to a valid search space
    # Only run this if user_id column exists on llm_configs
    if "user_id" in llm_config_columns:
        op.execute(
            """
            UPDATE llm_configs lc
            SET search_space_id = (
                SELECT id 
                FROM searchspaces ss 
                WHERE ss.user_id = lc.user_id 
                ORDER BY ss.created_at ASC 
                LIMIT 1
            )
            WHERE search_space_id IS NULL AND user_id IS NOT NULL
            """
        )

    # ===== STEP 3: Make search_space_id NOT NULL and add FK constraint =====
    # Check if there are any rows with NULL search_space_id
    # If llm_configs table is empty or all rows have search_space_id, we can proceed
    result = conn.execute(
        sa.text("SELECT COUNT(*) FROM llm_configs WHERE search_space_id IS NULL")
    )
    null_count = result.scalar()

    if null_count == 0 or "user_id" in llm_config_columns:
        # Safe to make NOT NULL
        op.alter_column(
            "llm_configs",
            "search_space_id",
            nullable=False,
        )
    else:
        # If there are NULL values and no user_id to migrate from, skip making it NOT NULL
        # This would happen if llm_configs already exists without user_id
        pass

    # Add foreign key constraint only if search_space_id is NOT NULL
    foreign_keys = [fk["name"] for fk in inspector.get_foreign_keys("llm_configs")]
    if "fk_llm_configs_search_space_id" not in foreign_keys and null_count == 0:
        op.create_foreign_key(
            "fk_llm_configs_search_space_id",
            "llm_configs",
            "searchspaces",
            ["search_space_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Drop old user_id foreign key if it exists
    if "fk_llm_configs_user_id_user" in foreign_keys:
        op.drop_constraint(
            "fk_llm_configs_user_id_user",
            "llm_configs",
            type_="foreignkey",
        )

    # Remove user_id column
    if "user_id" in llm_config_columns:
        op.drop_column("llm_configs", "user_id")

    # ===== STEP 4: Create user_search_space_preferences table =====
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'user_search_space_preferences'
            ) THEN
                CREATE TABLE user_search_space_preferences (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
                    long_context_llm_id INTEGER REFERENCES llm_configs(id) ON DELETE SET NULL,
                    fast_llm_id INTEGER REFERENCES llm_configs(id) ON DELETE SET NULL,
                    strategic_llm_id INTEGER REFERENCES llm_configs(id) ON DELETE SET NULL,
                    CONSTRAINT uq_user_searchspace UNIQUE (user_id, search_space_id)
                );
            END IF;
        END$$;
        """
    )

    # Create indexes
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_search_space_preferences' 
                AND indexname = 'ix_user_search_space_preferences_id'
            ) THEN
                CREATE INDEX ix_user_search_space_preferences_id 
                ON user_search_space_preferences(id);
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'user_search_space_preferences' 
                AND indexname = 'ix_user_search_space_preferences_created_at'
            ) THEN
                CREATE INDEX ix_user_search_space_preferences_created_at 
                ON user_search_space_preferences(created_at);
            END IF;
        END$$;
        """
    )

    # ===== STEP 5: Migrate user LLM preferences to user_search_space_preferences =====
    # For each user, create preferences for each of their search spaces
    if all(
        col in user_columns
        for col in ["long_context_llm_id", "fast_llm_id", "strategic_llm_id"]
    ):
        op.execute(
            """
            INSERT INTO user_search_space_preferences 
                (user_id, search_space_id, long_context_llm_id, fast_llm_id, strategic_llm_id, created_at)
            SELECT 
                u.id as user_id,
                ss.id as search_space_id,
                u.long_context_llm_id,
                u.fast_llm_id,
                u.strategic_llm_id,
                NOW() as created_at
            FROM "user" u
            CROSS JOIN searchspaces ss
            WHERE ss.user_id = u.id
            ON CONFLICT (user_id, search_space_id) DO NOTHING
            """
        )

    # ===== STEP 6: Remove LLM preference columns from user table =====
    # Get fresh list of foreign keys after previous operations
    user_foreign_keys = [fk["name"] for fk in inspector.get_foreign_keys("user")]

    # Drop foreign key constraints if they exist
    if "fk_user_long_context_llm_id_llm_configs" in user_foreign_keys:
        op.drop_constraint(
            "fk_user_long_context_llm_id_llm_configs",
            "user",
            type_="foreignkey",
        )

    if "fk_user_fast_llm_id_llm_configs" in user_foreign_keys:
        op.drop_constraint(
            "fk_user_fast_llm_id_llm_configs",
            "user",
            type_="foreignkey",
        )

    if "fk_user_strategic_llm_id_llm_configs" in user_foreign_keys:
        op.drop_constraint(
            "fk_user_strategic_llm_id_llm_configs",
            "user",
            type_="foreignkey",
        )

    # Drop columns from user table
    if "long_context_llm_id" in user_columns:
        op.drop_column("user", "long_context_llm_id")

    if "fast_llm_id" in user_columns:
        op.drop_column("user", "fast_llm_id")

    if "strategic_llm_id" in user_columns:
        op.drop_column("user", "strategic_llm_id")


def downgrade() -> None:
    """
    Downgrade schema back to user-owned LLM configs.

    WARNING: This downgrade will result in data loss:
    - LLM configs will be moved back to user ownership (first occurrence kept)
    - Per-search-space user preferences will be consolidated to user level
    - Additional LLM configs in search spaces beyond the first will be deleted
    """

    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)

    # Get existing columns and constraints
    llm_config_columns = [col["name"] for col in inspector.get_columns("llm_configs")]
    user_columns = [col["name"] for col in inspector.get_columns("user")]

    # ===== STEP 1: Add LLM preference columns back to user table =====
    if "long_context_llm_id" not in user_columns:
        op.add_column(
            "user",
            sa.Column("long_context_llm_id", sa.Integer(), nullable=True),
        )

    if "fast_llm_id" not in user_columns:
        op.add_column(
            "user",
            sa.Column("fast_llm_id", sa.Integer(), nullable=True),
        )

    if "strategic_llm_id" not in user_columns:
        op.add_column(
            "user",
            sa.Column("strategic_llm_id", sa.Integer(), nullable=True),
        )

    # ===== STEP 2: Migrate preferences back to user table =====
    # Take the first preference for each user
    op.execute(
        """
        UPDATE "user" u
        SET 
            long_context_llm_id = ussp.long_context_llm_id,
            fast_llm_id = ussp.fast_llm_id,
            strategic_llm_id = ussp.strategic_llm_id
        FROM (
            SELECT DISTINCT ON (user_id) 
                user_id,
                long_context_llm_id,
                fast_llm_id,
                strategic_llm_id
            FROM user_search_space_preferences
            ORDER BY user_id, created_at ASC
        ) ussp
        WHERE u.id = ussp.user_id
        """
    )

    # ===== STEP 3: Add foreign key constraints back to user table =====
    op.create_foreign_key(
        "fk_user_long_context_llm_id_llm_configs",
        "user",
        "llm_configs",
        ["long_context_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        "fk_user_fast_llm_id_llm_configs",
        "user",
        "llm_configs",
        ["fast_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        "fk_user_strategic_llm_id_llm_configs",
        "user",
        "llm_configs",
        ["strategic_llm_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ===== STEP 4: Drop user_search_space_preferences table =====
    op.execute("DROP TABLE IF EXISTS user_search_space_preferences CASCADE")

    # ===== STEP 5: Add user_id back to llm_configs =====
    if "user_id" not in llm_config_columns:
        op.add_column(
            "llm_configs",
            sa.Column("user_id", postgresql.UUID(), nullable=True),
        )

    # Populate user_id from search_space
    op.execute(
        """
        UPDATE llm_configs lc
        SET user_id = ss.user_id
        FROM searchspaces ss
        WHERE lc.search_space_id = ss.id
        """
    )

    # Make user_id NOT NULL
    op.alter_column(
        "llm_configs",
        "user_id",
        nullable=False,
    )

    # Add foreign key constraint for user_id
    op.create_foreign_key(
        "fk_llm_configs_user_id_user",
        "llm_configs",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ===== STEP 6: Remove search_space_id from llm_configs =====
    # Drop foreign key constraint
    foreign_keys = [fk["name"] for fk in inspector.get_foreign_keys("llm_configs")]
    if "fk_llm_configs_search_space_id" in foreign_keys:
        op.drop_constraint(
            "fk_llm_configs_search_space_id",
            "llm_configs",
            type_="foreignkey",
        )

    # Drop search_space_id column
    if "search_space_id" in llm_config_columns:
        op.drop_column("llm_configs", "search_space_id")
