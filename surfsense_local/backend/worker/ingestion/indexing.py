from sqlalchemy import delete, text
from sqlalchemy.orm import Session
from sqlite_vec import serialize_float32

from modules.chunks.models import Chunk
from modules.documents.models import Document
from worker.ingestion.chunking import Passage


def replace_chunks(
    session: Session,
    document: Document,
    passages: list[Passage],
    vectors: list[list[float]],
) -> None:
    """Swap a document's chunks and their vectors for a fresh set."""
    # The delete trigger clears both indexes for the old rows.
    session.execute(delete(Chunk).where(Chunk.document_id == document.id))

    rows = [
        Chunk(
            document_id=document.id,
            position=position,
            content=passage.text,
            embedding=serialize_float32(vector),
            start_line=passage.start_line,
            end_line=passage.end_line,
        )
        for position, (passage, vector) in enumerate(
            zip(passages, vectors, strict=True)
        )
    ]
    session.add_all(rows)
    session.flush()  # The vector rows key on chunk ids, assigned here.

    if rows:
        session.execute(
            text(
                "INSERT INTO chunk_vectors(rowid, embedding) VALUES (:id, :embedding)"
            ),
            [{"id": row.id, "embedding": row.embedding} for row in rows],
        )
