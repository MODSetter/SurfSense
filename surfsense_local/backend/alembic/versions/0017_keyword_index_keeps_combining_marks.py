"""Keep a word's combining marks inside it when the keyword index splits text.

unicode61 ends a token at every combining mark unless `M*` is among its
categories, so Devanagari `स्कैनर` (scanner) was indexed as `स` + `नर`: letters,
not words. Since ADR 0031 the keyword leg weighs what fraction of a question a
chunk matched, and nearly every Hindi document holds nearly every Devanagari
letter, so those fragments did not merely fail to match, they voted.

The literal below is frozen, as a migration's is; `shared/tokenizer.py` states
the live rule and an integration test holds the two together. The index keeps
no text of its own, so this rebuilds from `chunks` and needs no re-embed.

Revision ID: 0017
Revises: 0016

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOKENIZER = "unicode61 categories 'L* N* Co M*'"


def _rebuild(tokenize: str | None) -> None:
    option = f', tokenize="{tokenize}"' if tokenize else ""
    op.execute("DROP TABLE chunks_fts")
    op.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        f"content, content='chunks', content_rowid='id'{option})"
    )
    op.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")


def upgrade() -> None:
    _rebuild(TOKENIZER)


def downgrade() -> None:
    _rebuild(None)
