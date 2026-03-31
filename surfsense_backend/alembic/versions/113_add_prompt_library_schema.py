"""add prompt library schema: is_public, default_prompt_slug, version, drop icon

Revision ID: 113
Revises: 112
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "113"
down_revision: str | None = "112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS"
        " is_public BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prompts_is_public"
        " ON prompts (is_public) WHERE is_public = true"
    )
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS"
        " default_prompt_slug VARCHAR(100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prompts_default_prompt_slug"
        " ON prompts (default_prompt_slug)"
    )
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = 'uq_prompt_user_default_slug'"
        )
    ).scalar()
    if not exists:
        op.execute(
            "ALTER TABLE prompts ADD CONSTRAINT uq_prompt_user_default_slug"
            " UNIQUE (user_id, default_prompt_slug)"
        )
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS"
        " version INTEGER NOT NULL DEFAULT 1"
    )
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS icon")


def downgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS icon VARCHAR(50)")
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS version")
    op.execute(
        "ALTER TABLE prompts DROP CONSTRAINT IF EXISTS uq_prompt_user_default_slug"
    )
    op.execute("DROP INDEX IF EXISTS ix_prompts_default_prompt_slug")
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS default_prompt_slug")
    op.execute("DROP INDEX IF EXISTS ix_prompts_is_public")
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS is_public")
