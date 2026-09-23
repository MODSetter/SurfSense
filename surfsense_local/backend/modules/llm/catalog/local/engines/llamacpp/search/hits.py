"""Searching Hugging Face for GGUF repos, described and never judged.

Ordered by downloads, the only sort usable as a default: every other one
surfaces abliterated derivatives or half finished uploads in the top few. The
count is popularity, never endorsement, and a hit carries no rank.
"""

from dataclasses import dataclass

import httpx

from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import ListedFile, preferred_projector

API = "https://huggingface.co/api/models"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@dataclass(frozen=True)
class SearchHit:
    repo: str
    downloads: int
    likes: int
    last_modified: str | None = None
    license: str | None = None
    gated: bool = False
    # Provenance, not a grade: 32 of the top 40 GGUF repos carry the
    # `base_model:quantized:<repo>` tag. Returned by the API and not shown on the
    # row: it names the exact parent repo, which for a QAT build is an
    # intermediate `...-unquantized` repo, and the repo's own name usually says
    # the same. Kept for a later reader, such as matching a typed search against
    # a repo's base model, which is what Unsloth Studio uses it for.
    quantized_from: str | None = None
    # The repo ships a vision projector, judged by its file names with the rule
    # a repo's builds use. A guess until the header is read before install.
    reads_images: bool = False


async def search_models(
    client: httpx.AsyncClient, query: str, *, limit: int = 30
) -> list[SearchHit]:
    reply = await client.get(
        API,
        params={
            "filter": "gguf",
            "search": query,
            "sort": "downloads",
            "direction": -1,
            "limit": min(limit, 50),
            "full": "true",
        },
        timeout=TIMEOUT,
    )
    reply.raise_for_status()
    return [_hit(row) for row in reply.json()]


def _hit(row: dict) -> SearchHit:
    tags = tuple(row.get("tags") or ())
    return SearchHit(
        repo=row.get("id", ""),
        downloads=row.get("downloads", 0),
        likes=row.get("likes", 0),
        last_modified=row.get("lastModified"),
        license=next(
            (t.removeprefix("license:") for t in tags if t.startswith("license:")), None
        ),
        gated=bool(row.get("gated")),
        quantized_from=next(
            (
                t.removeprefix("base_model:quantized:")
                for t in tags
                if t.startswith("base_model:quantized:")
            ),
            None,
        ),
        reads_images=_ships_projector(row),
    )


def _ships_projector(row: dict) -> bool:
    """`full=true` lists every file, so this needs no request of its own."""
    names = [
        ListedFile(sibling["rfilename"], 0)
        for sibling in row.get("siblings") or ()
        if isinstance(sibling, dict) and isinstance(sibling.get("rfilename"), str)
    ]
    return preferred_projector(names) is not None
