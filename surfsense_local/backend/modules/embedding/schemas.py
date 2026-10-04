from pydantic import BaseModel

from modules.embedding.spec import EmbedderSpec


class IndexRead(BaseModel):
    """One index: the spec its vectors were made with, and what to call it."""

    name: str
    spec: EmbedderSpec


class EmbeddingIndexRead(BaseModel):
    active: IndexRead | None
    # Always null until changing the model is built; carries its progress then.
    building: IndexRead | None = None
