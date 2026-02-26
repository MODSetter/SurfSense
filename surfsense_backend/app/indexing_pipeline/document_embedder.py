from app.config import config


def embed_text(text: str) -> list[float]:
    """Embed a single text string using the configured embedding model."""
    return config.embedding_model_instance.embed(text)
