"""Index the corpus in a throwaway database and ask it every query.

The index is built the way a user's is: migrations, then the ingest pipeline,
so chunking, embedding and both retrieval legs are the app's own.
"""

from dataclasses import asdict, dataclass

from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace
from retrieval_eval.cases import Corpus
from retrieval_eval.score import Ranking, score
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from shared.migrations import upgrade_to_head
from shared.search import retrieve

# Deeper than chat reads, so a miss can be told from a near miss.
DEPTH = 10


@dataclass(frozen=True)
class Result:
    query: str
    slice: str
    ranking: Ranking
    # What came back, for reading a failure without running it again.
    passages: list[str]
    titles: list[str]


def open_index():
    """The workspace in an index built by an earlier run, or None."""
    database = get_storage_settings().database_path
    if not database.exists():
        return None
    engine = create_db_engine(database)
    session = create_session_factory(engine)()
    workspace = session.query(Workspace).first()
    if workspace is None:
        session.close()
        engine.dispose()
        return None
    return session, workspace.id, engine


def index(corpus: Corpus):
    """A workspace holding the corpus, every document ingested to ready.

    The database is the configured one, which the entry script points at a
    directory keyed by the corpus and the embedder: the ingest job opens its
    own engine from that setting, so both halves have to agree or nothing is
    indexed.

    Returns the engine too, because Windows will not delete the file while a
    pooled connection still holds it.
    """
    engine = create_db_engine(get_storage_settings().database_path)
    upgrade_to_head(engine)
    session = create_session_factory(engine)()
    workspace = Workspace(name="Retrieval eval")
    session.add(workspace)
    session.flush()
    # Imported here: it pulls onnxruntime and the embedding model.
    from worker.ingestion import run as ingest

    for document in corpus.documents:
        row = Document(
            workspace_id=workspace.id,
            title=document.title,
            document_type=DocumentType.NOTE,
            content=document.markdown,
        )
        session.add(row)
        session.commit()
        ingest(row.id)
    return session, workspace.id, engine


def ask(session, workspace_id: int, corpus: Corpus) -> list[Result]:
    results = []
    for query in corpus.queries:
        hits = retrieve(session, workspace_id, query.text, top_k=DEPTH)
        passages = [hit.content for hit in hits]
        results.append(
            Result(
                query=query.id,
                slice=query.slice,
                ranking=score(query, passages),
                passages=passages,
                titles=[hit.title for hit in hits],
            )
        )
    return results


def as_record(result: Result) -> dict:
    return {**asdict(result), "ranking": asdict(result.ranking)}
