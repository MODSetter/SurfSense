from fastapi import APIRouter
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.embedding.active import active_index
from modules.embedding.schemas import EmbeddingIndexRead, IndexRead
from modules.llm.catalog.local.manifest import load_local_manifest

router = APIRouter(prefix="/embedding", tags=["embedding"])


@router.get(
    "/index",
    response_model=EmbeddingIndexRead,
    summary="Read which embedding model the library is built with",
)
async def read_index(session: SessionDep) -> EmbeddingIndexRead:
    return await transact(session, _read)


def _read(session: Session) -> EmbeddingIndexRead:
    index = active_index(session)
    if index is None:
        return EmbeddingIndexRead(active=None)
    names = {m.id: m.name for m in load_local_manifest().models}
    return EmbeddingIndexRead(
        # A Hugging Face pick is named by its repo; its install name is ours.
        active=IndexRead(
            name=names.get(index.spec.id, index.spec.repo), spec=index.spec
        )
    )
