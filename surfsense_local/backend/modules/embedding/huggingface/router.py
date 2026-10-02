"""Embedders on Hugging Face: search, and one repo opened as an install.

Answered in the GGUF search's shapes, so onboarding renders both through one
list. Egress gated like that search: what the user types goes to a third party.
Downloading goes through the same install jobs as every local model.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.embedding.huggingface.resolve import resolve
from modules.embedding.huggingface.search import search
from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.engines.onnxruntime.rows import searched_row
from modules.llm.catalog.local.router import row_read
from modules.llm.catalog.local.rows import BuildRow
from modules.llm.catalog.local.schemas import RepoRead, SearchRead

router = APIRouter(prefix="/embedding/huggingface", tags=["embedding"])


@router.get("/search", response_model=SearchRead, summary="Search for embedders")
async def search_embedders(
    q: Annotated[str, Query(min_length=1, max_length=200)], session: SessionDep
) -> dict:
    await transact(session, egress.require, egress.HUGGINGFACE)
    return {"results": [hit.__dict__ for hit in await search(q)]}


@router.get(
    "/repo/{repo:path}", response_model=RepoRead, summary="Open one embedder repo"
)
async def open_repo(repo: str, service: LocalCatalogDep, session: SessionDep) -> dict:
    await transact(session, egress.require, egress.HUGGINGFACE)
    resolved = await resolve(repo)
    if resolved.picked is None or resolved.spec is None:
        row = searched_row(repo, None, resolved.reason)
        return {"repo": repo, "gated": resolved.gated, "row": row_read(row, {})}
    build = Build(
        "ONNX",
        tuple(
            BuildFile(
                FileRole.TOKENIZER
                if f is resolved.picked.tokenizer
                else FileRole.WEIGHTS,
                f.path,
                f.size_bytes,
                f.sha256,
                repo,
                resolved.revision or "main",
            )
            for f in resolved.picked.all
        ),
    )
    # Installed means checked: files without a settled spec are not a pick.
    held = service.onnxruntime.installed_spec(resolved.spec.id) is not None
    offered = BuildRow(
        catalog_id=service.offer_embedder(build, resolved.spec),
        build=build,
        fit=None,
        badge=None,
        installed_as=resolved.spec.id if held else None,
        recommended=False,
        reads_images=False,
        projector_checked=False,
    )
    row = searched_row(repo, offered, None)
    return {"repo": repo, "gated": False, "row": row_read(row, {})}
