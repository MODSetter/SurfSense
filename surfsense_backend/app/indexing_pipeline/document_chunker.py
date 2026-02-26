from app.config import config


def chunk_text(text: str, use_code_chunker: bool = False) -> list[str]:
    """Chunk a text string using the configured chunker and return the chunk texts."""
    chunker = (
        config.code_chunker_instance if use_code_chunker else config.chunker_instance
    )
    return [c.text for c in chunker.chunk(text)]
