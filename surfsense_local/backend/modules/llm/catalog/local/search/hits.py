"""Searching Hugging Face for GGUF repos, described and never judged.

Ordered by downloads, the only sort usable as a default: every other one
surfaces abliterated derivatives or half finished uploads in the top few. The
count is popularity, never endorsement, and a hit carries no rank.
"""

from dataclasses import dataclass

import httpx

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
    # Provenance, not a grade: 32 of the top 40 GGUF repos carry this tag.
    quantized_from: str | None = None


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
    )
