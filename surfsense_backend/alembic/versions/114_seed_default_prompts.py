"""seed default prompts for all existing users

Revision ID: 114
Revises: 113
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "114"
down_revision: str | None = "113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO prompts
                (user_id, default_prompt_slug, name, prompt, mode, version, is_public, created_at)
            SELECT u.id, d.slug, d.name, d.prompt, d.mode::prompt_mode, 1, false, now()
            FROM "user" u
            CROSS JOIN (VALUES
                ('fix-grammar',       'Fix grammar',           'Fix the grammar and spelling in the following text. Return only the corrected text, nothing else.\n\n{selection}',                              'transform'),
                ('make-shorter',      'Make shorter',          'Make the following text more concise while preserving its meaning. Return only the shortened text, nothing else.\n\n{selection}',                'transform'),
                ('translate',         'Translate',             'Translate the following text to English. If it is already in English, translate it to French. Return only the translation, nothing else.\n\n{selection}', 'transform'),
                ('rewrite',           'Rewrite',               'Rewrite the following text to improve clarity and readability. Return only the rewritten text, nothing else.\n\n{selection}',                    'transform'),
                ('summarize',         'Summarize',             'Summarize the following text concisely. Return only the summary, nothing else.\n\n{selection}',                                                  'transform'),
                ('explain',           'Explain',               'Explain the following text in simple terms:\n\n{selection}',                                                                                     'explore'),
                ('ask-knowledge-base','Ask my knowledge base', 'Search my knowledge base for information related to:\n\n{selection}',                                                                            'explore'),
                ('look-up-web',       'Look up on the web',    'Search the web for information about:\n\n{selection}',                                                                                           'explore')
            ) AS d(slug, name, prompt, mode)
            ON CONFLICT (user_id, default_prompt_slug) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM prompts WHERE default_prompt_slug IS NOT NULL")
