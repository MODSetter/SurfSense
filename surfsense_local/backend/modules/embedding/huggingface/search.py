"""Embedders on Hugging Face by name, described and not yet judged.

Whether one can run here needs its file list, read when it is opened. Hits take
the GGUF search's shape, so both searches render through one list.
"""

import asyncio

from modules.embedding.huggingface import hub
from modules.llm.catalog.local.engines.llamacpp.search.hits import SearchHit

# The two tags an embedder carries; the search API takes one at a time.
TAGS = ("sentence-similarity", "feature-extraction")
LIMIT = 20


async def search(query: str) -> list[SearchHit]:
    async with hub.client() as client:
        replies = await asyncio.gather(
            *(
                client.get(
                    "/api/models",
                    params={
                        "search": query,
                        "pipeline_tag": tag,
                        "limit": LIMIT,
                        "expand[]": [
                            "downloads",
                            "likes",
                            "lastModified",
                            "gated",
                            "tags",
                        ],
                    },
                )
                for tag in TAGS
            )
        )
    found: dict[str, SearchHit] = {}
    for reply in replies:
        reply.raise_for_status()
        for row in reply.json():
            found.setdefault(row["id"], _hit(row))
    return sorted(found.values(), key=lambda hit: -hit.downloads)[:LIMIT]


def _hit(row: dict) -> SearchHit:
    tags = tuple(row.get("tags") or ())
    return SearchHit(
        repo=row["id"],
        downloads=int(row.get("downloads") or 0),
        likes=int(row.get("likes") or 0),
        last_modified=row.get("lastModified"),
        license=next(
            (t.removeprefix("license:") for t in tags if t.startswith("license:")), None
        ),
        gated=bool(row.get("gated")),
    )
