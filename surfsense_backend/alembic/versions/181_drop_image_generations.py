"""Drop the legacy image_generations table now that images live in Artifacts.

The ``generate_image`` tool writes an Artifact directly and no longer inserts
here; historical rows move over via ``scripts/backfill_image_artifacts.py``.
Run that with --yes before this migration or the images are lost.

Guarded like 180: refuses to drop while any convertible row (one that still
holds ``response_data``) has no Artifact. Rows that only ever held an error
carry no image, so they don't block the drop. The image *config* table and
the ``imagegenprovider`` enum are untouched — the tool still uses them.

Revision ID: 181
Revises: 180
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "181"
down_revision: str | None = "180"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pending = (
        op.get_bind()
        .execute(
            text(
                """
                SELECT count(*) FROM image_generations ig
                WHERE ig.response_data IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM artifacts a
                    WHERE a.format = 'image'
                      AND a.metadata -> 'legacy' ->> 'kind' = 'image'
                      AND (a.metadata -> 'legacy' ->> 'id')::int = ig.id
                  )
                """
            )
        )
        .scalar()
    )
    if pending:
        raise RuntimeError(
            f"{pending} image_generations row(s) with image data have no Artifact. "
            "Run `python -m scripts.backfill_image_artifacts --yes` before this "
            "migration, or those images will be lost."
        )

    op.execute("DROP INDEX IF EXISTS ix_image_generations_access_token")
    op.execute("DROP INDEX IF EXISTS ix_image_generations_created_at")
    op.execute("DROP INDEX IF EXISTS ix_image_generations_created_by_id")
    op.execute("DROP INDEX IF EXISTS ix_image_generations_workspace_id")
    op.execute("DROP INDEX IF EXISTS ix_image_generations_search_space_id")
    op.execute("DROP TABLE IF EXISTS image_generations")

    op.execute(
        """
        UPDATE workspace_roles
        SET permissions = array_remove(
            array_remove(
                array_remove(permissions, 'image_generations:create'),
                'image_generations:read'
            ),
            'image_generations:delete'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_generations (
            id SERIAL PRIMARY KEY,
            prompt TEXT NOT NULL,
            model VARCHAR(200),
            n INTEGER,
            quality VARCHAR(50),
            size VARCHAR(50),
            style VARCHAR(50),
            response_format VARCHAR(50),
            image_gen_model_id INTEGER,
            response_data JSONB,
            error_message TEXT,
            access_token VARCHAR(64),
            workspace_id INTEGER NOT NULL
                REFERENCES workspaces(id) ON DELETE CASCADE,
            created_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_workspace_id "
        "ON image_generations (workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_created_by_id "
        "ON image_generations (created_by_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_created_at "
        "ON image_generations (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_generations_access_token "
        "ON image_generations (access_token)"
    )

    # Restore the grants migration 93 gave the system roles.
    op.execute(
        """
        UPDATE workspace_roles
        SET permissions = array_cat(
            permissions,
            ARRAY['image_generations:create', 'image_generations:read']
        )
        WHERE is_system_role = true AND name = 'Editor'
          AND NOT ('image_generations:read' = ANY(permissions))
        """
    )
    op.execute(
        """
        UPDATE workspace_roles
        SET permissions = array_cat(permissions, ARRAY['image_generations:read'])
        WHERE is_system_role = true AND name = 'Viewer'
          AND NOT ('image_generations:read' = ANY(permissions))
        """
    )
