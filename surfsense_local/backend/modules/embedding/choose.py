"""What finishing onboarding fixes as the library's embedder."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.embedding.active import active_index
from modules.embedding.bundled import BGE
from modules.embedding.lock import lock_index
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.catalog.local.engines.onnxruntime.spec import spec_for
from modules.llm.catalog.local.manifest import load_local_manifest


def lock_chosen(session: Session, model_id: str | None) -> None:
    """The curated embedder onboarding chose, or bge when it chose none.

    Once locked, the same choice again is a no-op and any other is refused:
    changing the embedder is a re-embed, which is not built.
    """
    chosen = model_id or BGE.id
    active = active_index(session)
    if active is not None:
        if model_id is not None and active.spec.id != chosen:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{active.spec.id} is already this library's embedding model",
            )
        return
    if chosen == BGE.id:
        lock_index(session, BGE)
        return
    picked = get_local_catalog().onnxruntime.installed_spec(chosen)
    if picked is not None:
        lock_index(session, picked)
        return
    model = next(
        (
            m
            for m in load_local_manifest().models
            if m.id == chosen and m.embedding is not None
        ),
        None,
    )
    if model is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"no curated embedding model named {chosen}",
        )
    if not get_local_catalog().onnxruntime.holds(chosen):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{chosen} has not finished downloading"
        )
    lock_index(session, spec_for(model))
