"""add default_prompt_slug, version, drop icon, seed defaults

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

DEFAULTS = [
    (
        "fix-grammar",
        "Fix grammar",
        "Fix the grammar and spelling in the following text. Return only the corrected text, nothing else.\n\n{selection}",
        "transform",
    ),
    (
        "make-shorter",
        "Make shorter",
        "Make the following text more concise while preserving its meaning. Return only the shortened text, nothing else.\n\n{selection}",
        "transform",
    ),
    (
        "translate",
        "Translate",
        "Translate the following text to English. If it is already in English, translate it to French. Return only the translation, nothing else.\n\n{selection}",
        "transform",
    ),
    (
        "rewrite",
        "Rewrite",
        "Rewrite the following text to improve clarity and readability. Return only the rewritten text, nothing else.\n\n{selection}",
        "transform",
    ),
    (
        "summarize",
        "Summarize",
        "Summarize the following text concisely. Return only the summary, nothing else.\n\n{selection}",
        "transform",
    ),
    (
        "explain",
        "Explain",
        "Explain the following text in simple terms:\n\n{selection}",
        "explore",
    ),
    (
        "ask-knowledge-base",
        "Ask my knowledge base",
        "Search my knowledge base for information related to:\n\n{selection}",
        "explore",
    ),
    (
        "look-up-web",
        "Look up on the web",
        "Search the web for information about:\n\n{selection}",
        "explore",
    ),
]


def upgrade() -> None:
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS default_prompt_slug VARCHAR(100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prompts_default_prompt_slug"
        " ON prompts (default_prompt_slug)"
    )
    op.execute(
        "ALTER TABLE prompts ADD CONSTRAINT uq_prompt_user_default_slug"
        " UNIQUE (user_id, default_prompt_slug)"
    )
    op.execute(
        "ALTER TABLE prompts ADD COLUMN IF NOT EXISTS"
        " version INTEGER NOT NULL DEFAULT 1"
    )
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS icon")

    conn = op.get_bind()
    users = conn.execute(sa.text('SELECT id FROM "user"')).fetchall()

    for user_row in users:
        user_id = user_row[0]
        for slug, name, prompt, mode in DEFAULTS:
            conn.execute(
                sa.text(
                    "INSERT INTO prompts"
                    " (user_id, default_prompt_slug, name, prompt, mode, version, is_public, created_at)"
                    " VALUES (:user_id, :slug, :name, :prompt, :mode::prompt_mode, :version, false, now())"
                    " ON CONFLICT (user_id, default_prompt_slug) DO NOTHING"
                ),
                {
                    "user_id": user_id,
                    "slug": slug,
                    "name": name,
                    "prompt": prompt,
                    "mode": mode,
                    "version": 1,
                },
            )


def downgrade() -> None:
    op.execute("DELETE FROM prompts WHERE default_prompt_slug IS NOT NULL")
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS icon VARCHAR(50)")
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS version")
    op.execute(
        "ALTER TABLE prompts DROP CONSTRAINT IF EXISTS uq_prompt_user_default_slug"
    )
    op.execute("DROP INDEX IF EXISTS ix_prompts_default_prompt_slug")
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS default_prompt_slug")
