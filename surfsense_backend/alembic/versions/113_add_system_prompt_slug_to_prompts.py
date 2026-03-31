"""add system_prompt_slug and drop icon from prompts

Revision ID: 113
Revises: 112
"""

from collections.abc import Sequence

from alembic import op

revision: str = "113"
down_revision: str | None = "112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS"
        " system_prompt_slug VARCHAR(100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prompts_system_prompt_slug"
        " ON prompts (system_prompt_slug)"
    )
    op.execute(
        "ALTER TABLE prompts ADD CONSTRAINT uq_prompt_user_system_slug"
        " UNIQUE (user_id, system_prompt_slug)"
    )
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS icon")


def downgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS icon VARCHAR(50)")
    op.execute(
        "ALTER TABLE prompts DROP CONSTRAINT IF EXISTS uq_prompt_user_system_slug"
    )
    op.execute("DROP INDEX IF EXISTS ix_prompts_system_prompt_slug")
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS system_prompt_slug")
