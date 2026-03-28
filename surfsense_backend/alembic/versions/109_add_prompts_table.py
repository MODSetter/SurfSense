"""add prompts table

Revision ID: 109
Revises: 108
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "109"
down_revision: str | None = "108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'prompt_mode'")
    )
    if not result.fetchone():
        op.execute("CREATE TYPE prompt_mode AS ENUM ('transform', 'explore')")

    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = 'prompts'")
    )
    if not result.fetchone():
        op.execute("""
            CREATE TABLE prompts (
                id SERIAL PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
                name VARCHAR(200) NOT NULL,
                prompt TEXT NOT NULL,
                mode prompt_mode NOT NULL,
                icon VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        op.execute("CREATE INDEX ix_prompts_user_id ON prompts (user_id)")
        op.execute("CREATE INDEX ix_prompts_search_space_id ON prompts (search_space_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS prompts")
    op.execute("DROP TYPE IF EXISTS prompt_mode")
