"""The one rule by which text becomes terms, for the index and the question alike.

A term the index keeps whole and a question cuts up matches nothing. Since
[ADR 0031](../../../docs/adr/0031-ranking-blends-absolute-leg-scores.md) the
keyword leg scores what fraction of a question a chunk matched, so a
disagreement no longer merely misses: it votes. FTS5 itself is asked rather
than matched by a regex, which would have to track its case folding and its
Latin diacritic table to stay honest.
"""

import sqlite3

# `M*` keeps a combining mark inside its word. Without it unicode61 ends a token
# at every mark, so Devanagari `स्कैनर` indexes as `स` + `नर`: letters, not
# words, and nearly every Hindi document holds nearly every letter. Latin,
# digits and identifiers tokenise the same either way.
TOKENIZER = "unicode61 categories 'L* N* Co M*'"


def terms(text: str) -> list[str]:
    """The distinct terms FTS5 indexes for `text`, sorted.

    Distinct because coverage asks what fraction of a question a chunk matched,
    which a word repeated in the question must not inflate.
    """
    # ponytail: a throwaway connection per call, ~355us against the ~50ms the
    # query's own embedding costs, and retrieve() calls this once. Hold one in a
    # threading.local (~31us) if it ever runs in a loop.
    db = sqlite3.connect(":memory:")
    db.execute(f'CREATE VIRTUAL TABLE q USING fts5(body, tokenize="{TOKENIZER}")')
    db.execute("CREATE VIRTUAL TABLE v USING fts5vocab(q, row)")
    db.execute("INSERT INTO q(body) VALUES (?)", (text,))
    return [term for (term,) in db.execute("SELECT term FROM v")]
