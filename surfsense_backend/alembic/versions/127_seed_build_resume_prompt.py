"""127_seed_build_resume_prompt

Revision ID: 127
Revises: 126
Create Date: 2026-04-15

Seeds the 'Build Resume' default prompt for all existing users.
New users get it automatically via SYSTEM_PROMPT_DEFAULTS on signup.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "127"
down_revision: str | None = "126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO prompts
                (user_id, default_prompt_slug, name, prompt, mode, version, is_public, created_at)
            SELECT u.id, 'build-resume', 'Build Resume',
                   E'Build me a professional resume. Here is my information:\\n\\n{selection}',
                   'explore'::prompt_mode, 1, false, now()
            FROM "user" u
            ON CONFLICT (user_id, default_prompt_slug) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM prompts WHERE default_prompt_slug = 'build-resume'")
