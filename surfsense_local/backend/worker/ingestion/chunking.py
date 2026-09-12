from functools import lru_cache
from typing import Any, NamedTuple

from chonkie import RecursiveChunker, RecursiveLevel, RecursiveRules

# Under bge-small's 512-token limit, with room for the two it adds per input.
CHUNK_TOKENS = 480


class Passage(NamedTuple):
    """A stretch of the document, and where it was found in it."""

    text: str
    start_line: int
    end_line: int


def chunk(
    markdown: str, *, tokenizer: Any = None, chunk_size: int = CHUNK_TOKENS
) -> list[Passage]:
    """Split markdown into passages the embedder can take whole."""
    if not markdown.strip():
        return []

    chunker = RecursiveChunker(
        tokenizer=tokenizer if tokenizer is not None else _default_tokenizer(),
        chunk_size=chunk_size,
        rules=_rules(),
        min_characters_per_chunk=24,
    )

    passages = (_passage(markdown, piece) for piece in chunker.chunk(markdown))
    return [passage for passage in passages if passage.text]


@lru_cache(maxsize=1)
def _rules() -> RecursiveRules:
    # Coarsest boundary first: heading, paragraph, line, sentence, word, then a
    # bare split so an over-budget line still terminates.
    return RecursiveRules(
        levels=[
            RecursiveLevel(delimiters=["\n#"], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="prev"),
            RecursiveLevel(delimiters=["\n"], include_delim="prev"),
            RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
            RecursiveLevel(whitespace=True),
            RecursiveLevel(),
        ]
    )


def _default_tokenizer() -> Any:
    # The embedder's own tokenizer, so the budget is what the model measures.
    from worker.ingestion.embedding import tokenizer

    return tokenizer()


def _passage(markdown: str, piece: Any) -> Passage:
    """Trim the separators Chonkie carries, and place the text by line."""
    lead = len(piece.text) - len(piece.text.lstrip())
    trail = len(piece.text) - len(piece.text.rstrip())
    start = piece.start_index + lead
    end = piece.end_index - trail

    return Passage(
        piece.text.strip(),
        markdown.count("\n", 0, start) + 1,
        markdown.count("\n", 0, max(start, end - 1)) + 1,
    )
