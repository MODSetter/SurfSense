"""Fixing the library's embedder, once, when onboarding finishes.

The one place outside migrations that emits DDL: the vector table's width is the
chosen model's, which no migration can know. Safe only while the table is empty,
which is what the refusals guarantee.
"""

from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session

from modules.chunks.models import Chunk
from modules.embedding.active import active_index
from modules.embedding.bundled import BGE
from modules.embedding.models import EmbeddingIndex, IndexState
from modules.embedding.spec import EmbedderSpec

# The table migration 0001 created, which the chunk delete trigger names.
FIRST_TABLE = "chunk_vectors"


class IndexAlreadyBuiltError(Exception):
    """The library already has vectors from some model, or a locked choice."""


def lock_index(session: Session, spec: EmbedderSpec) -> EmbeddingIndex:
    if session.scalar(
        select(exists().where(EmbeddingIndex.state == IndexState.ACTIVE))
    ):
        raise IndexAlreadyBuiltError("an embedding model is already chosen")
    if session.scalar(select(exists().select_from(Chunk))):
        raise IndexAlreadyBuiltError("the library already holds embedded passages")

    session.execute(text(f"DROP TABLE IF EXISTS {FIRST_TABLE}"))
    session.execute(
        text(
            f"CREATE VIRTUAL TABLE {FIRST_TABLE} "
            f"USING vec0(embedding float[{int(spec.dimension)}])"
        )
    )
    index = EmbeddingIndex(
        spec=spec.model_dump(mode="json"),
        vector_table=FIRST_TABLE,
        state=IndexState.ACTIVE,
    )
    session.add(index)
    session.flush()
    return index


def lock_default_if_unchosen(session: Session) -> None:
    """Finishing onboarding with no embedder chosen means the bundled one."""
    if active_index(session) is None:
        lock_index(session, BGE)
