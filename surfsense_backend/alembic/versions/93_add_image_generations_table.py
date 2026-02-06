"""Add image generation tables and search space preference

Revision ID: 93
Revises: 92

Changes:
1. Create image_generation_configs table (user-created image model configs)
2. Create image_generations table (stores generation requests/results)
3. Add image_generation_config_id column to searchspaces table
4. Add image generation permissions to existing system roles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "93"
down_revision: str | None = "92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Create imagegenprovider enum type if it doesn't exist
    connection.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'imagegenprovider') THEN
                    CREATE TYPE imagegenprovider AS ENUM (
                        'OPENAI', 'AZURE_OPENAI', 'GOOGLE', 'VERTEX_AI', 'BEDROCK',
                        'RECRAFT', 'OPENROUTER', 'XINFERENCE', 'NSCALE'
                    );
                END IF;
            END
            $$;
            """
        )
    )

    # 2. Create image_generation_configs table (uses imagegenprovider enum)
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'image_generation_configs')"
        )
    )
    if not result.scalar():
        op.create_table(
            "image_generation_configs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column(
                "provider",
                PG_ENUM(
                    "OPENAI",
                    "AZURE_OPENAI",
                    "GOOGLE",
                    "VERTEX_AI",
                    "BEDROCK",
                    "RECRAFT",
                    "OPENROUTER",
                    "XINFERENCE",
                    "NSCALE",
                    name="imagegenprovider",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("custom_provider", sa.String(100), nullable=True),
            sa.Column("model_name", sa.String(100), nullable=False),
            sa.Column("api_key", sa.String(), nullable=False),
            sa.Column("api_base", sa.String(500), nullable=True),
            sa.Column("api_version", sa.String(50), nullable=True),
            sa.Column("litellm_params", sa.JSON(), nullable=True),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_image_generation_configs_name "
            "ON image_generation_configs (name)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_image_generation_configs_search_space_id "
            "ON image_generation_configs (search_space_id)"
        )

    # 3. Create image_generations table
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'image_generations')"
        )
    )
    if not result.scalar():
        op.create_table(
            "image_generations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("model", sa.String(200), nullable=True),
            sa.Column("n", sa.Integer(), nullable=True),
            sa.Column("quality", sa.String(50), nullable=True),
            sa.Column("size", sa.String(50), nullable=True),
            sa.Column("style", sa.String(50), nullable=True),
            sa.Column("response_format", sa.String(50), nullable=True),
            sa.Column("image_generation_config_id", sa.Integer(), nullable=True),
            sa.Column("response_data", JSONB(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("created_by_id", UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["user.id"], ondelete="SET NULL"
            ),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_search_space_id "
        "ON image_generations (search_space_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_created_by_id "
        "ON image_generations (created_by_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_created_at "
        "ON image_generations (created_at)"
    )

    # 4. Add image_generation_config_id column to searchspaces
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces'
                  AND column_name = 'image_generation_config_id'
            )
            """
        )
    )
    if not result.scalar():
        op.add_column(
            "searchspaces",
            sa.Column(
                "image_generation_config_id",
                sa.Integer(),
                nullable=True,
                server_default="0",
            ),
        )

    # Drop old column name if it exists (from earlier version of this migration)
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces'
                  AND column_name = 'image_generation_llm_id'
            )
            """
        )
    )
    if result.scalar():
        op.drop_column("searchspaces", "image_generation_llm_id")

    # Drop old column name on image_generations if it exists
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'image_generations'
                  AND column_name = 'llm_config_id'
            )
            """
        )
    )
    if result.scalar():
        op.drop_column("image_generations", "llm_config_id")

    # Drop old api_version column on image_generations if it exists
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'image_generations'
                  AND column_name = 'api_version'
            )
            """
        )
    )
    if result.scalar():
        op.drop_column("image_generations", "api_version")

    # 5. Add image generation permissions to existing system roles
    connection.execute(
        sa.text(
            """
            UPDATE search_space_roles
            SET permissions = array_cat(
                permissions,
                ARRAY['image_generations:create', 'image_generations:read']
            )
            WHERE is_system_role = true
              AND name = 'Editor'
              AND NOT ('image_generations:create' = ANY(permissions))
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE search_space_roles
            SET permissions = array_cat(
                permissions,
                ARRAY['image_generations:read']
            )
            WHERE is_system_role = true
              AND name = 'Viewer'
              AND NOT ('image_generations:read' = ANY(permissions))
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()

    # Remove permissions
    connection.execute(
        sa.text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(
                array_remove(
                    array_remove(permissions, 'image_generations:create'),
                    'image_generations:read'
                ),
                'image_generations:delete'
            )
            WHERE is_system_role = true
            """
        )
    )

    # Remove image_generation_config_id from searchspaces
    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces'
                  AND column_name = 'image_generation_config_id'
            )
            """
        )
    )
    if result.scalar():
        op.drop_column("searchspaces", "image_generation_config_id")

    # Drop indexes and tables
    op.execute("DROP INDEX IF EXISTS ix_image_generations_created_at")
    op.execute("DROP INDEX IF EXISTS ix_image_generations_created_by_id")
    op.execute("DROP INDEX IF EXISTS ix_image_generations_search_space_id")
    op.execute("DROP TABLE IF EXISTS image_generations")

    op.execute("DROP INDEX IF EXISTS ix_image_generation_configs_search_space_id")
    op.execute("DROP INDEX IF EXISTS ix_image_generation_configs_name")
    op.execute("DROP TABLE IF EXISTS image_generation_configs")

    # Drop the imagegenprovider enum type
    op.execute("DROP TYPE IF EXISTS imagegenprovider")
