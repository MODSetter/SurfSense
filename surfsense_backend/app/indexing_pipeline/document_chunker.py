import re

from app.config import config

# Regex that matches a Markdown table block (header + separator + one or more rows)
# A table block starts with a | at the beginning of a line and ends when a
# non-table line (or end of string) is encountered.
_TABLE_BLOCK_RE = re.compile(
    r"(?:(?:^|\n)(?=[ \t]*\|)(?:[ \t]*\|[^\n]*\n)+)",
    re.MULTILINE,
)


def chunk_text(text: str, use_code_chunker: bool = False) -> list[str]:
    """Chunk a text string using the configured chunker and return the chunk texts."""
    chunker = (
        config.code_chunker_instance if use_code_chunker else config.chunker_instance
    )
    return [c.text for c in chunker.chunk(text)]


def chunk_text_hybrid(text: str) -> list[str]:
    """Table-aware chunker that prevents Markdown tables from being split mid-row.

    Algorithm:
    1. Scan the document for Markdown table blocks.
    2. Each table block is emitted as a single, unmodified chunk so that its
       header, separator row, and data rows always stay together.
    3. The non-table prose segments between (and around) tables are passed through
       the normal ``chunk_text`` chunker and their sub-chunks are interleaved in
       document order.

    This ensures that table data is never sliced in the middle by the token-based
    chunker, which would otherwise produce garbled rows that are useless for RAG.

    Fixes #1334.
    """
    chunks: list[str] = []
    cursor = 0

    for match in _TABLE_BLOCK_RE.finditer(text):
        # Prose before this table
        prose = text[cursor : match.start()].strip()
        if prose:
            chunks.extend(chunk_text(prose))

        # The table itself is kept as one indivisible chunk
        table_block = match.group(0).strip()
        if table_block:
            chunks.append(table_block)

        cursor = match.end()

    # Remaining prose after the last table (or entire text if no tables)
    trailing = text[cursor:].strip()
    if trailing:
        chunks.extend(chunk_text(trailing))

    return chunks
