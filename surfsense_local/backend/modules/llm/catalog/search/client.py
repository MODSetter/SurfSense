"""Searching Hugging Face for anything llama.cpp can run.

204,797 GGUF repos, against the 240 of the registry this replaced. A network
feature and is simply **absent** when egress is off, which is the airgapped
product rather than a degraded one.

Ordered by downloads, which is the only sort usable as a default: every other
one surfaces abliterated derivatives or half finished uploads in the top few.
The count is presented as popularity, never as endorsement.
"""

import re
from dataclasses import dataclass, field

import httpx

API = "https://huggingface.co/api/models"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Hugging Face allows 500 requests per 5 minutes, and a search list is re-fetched
# on every keystroke a debounce lets through.
CACHE_SECONDS = 300


@dataclass(frozen=True)
class SearchHit:
    """A repo, described rather than judged.

    Carries **no rank and no quality claim**. Attaching one would put a base
    model's score on a derivative that behaves differently: of the top 100 GGUF
    repos by downloads, the matches include abliterated and uncensored builds
    resolving to their parent's number.
    """

    repo: str
    downloads: int
    likes: int
    last_modified: str | None = None
    license: str | None = None
    gated: bool = False
    # 32 of the top 40 GGUF repos carry a base_model:quantized:<repo> tag, so a
    # row can say where the file came from. That is a fact about provenance, not
    # a grade, and it is most of what a quality score was doing for a reader.
    quantized_from: str | None = None
    pipeline_tag: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


async def search_models(
    client: httpx.AsyncClient, query: str, *, limit: int = 30
) -> list[SearchHit]:
    """GGUF repos matching `query`, most downloaded first."""
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
        pipeline_tag=row.get("pipeline_tag"),
        tags=tags,
    )


@dataclass(frozen=True)
class RepoFile:
    """One build inside a repo."""

    file: str
    size_bytes: int
    quantization: str


async def list_builds(client: httpx.AsyncClient, repo: str) -> list[RepoFile]:
    """Every single file GGUF in a repo, with its exact size.

    Split sets, projectors and draft models are excluded rather than offered:
    none of them is a thing a user installs on its own.
    """
    reply = await client.get(
        f"{API}/{repo}/tree/main", params={"recursive": "true"}, timeout=TIMEOUT
    )
    reply.raise_for_status()

    builds = []
    for row in reply.json():
        path = row.get("path", "")
        lowered = path.lower()
        if not lowered.endswith(".gguf"):
            continue
        if "mmproj" in lowered or "draft" in lowered or "-of-" in path:
            continue
        builds.append(RepoFile(path, row.get("size", 0), _quantization(path)))
    return sorted(builds, key=lambda build: build.size_bytes)


# A quant name, not merely something that looks like one. Matching loosely reads
# "Qwen3" out of `Qwen3-Coder-30B-A3B-Instruct-UD-TQ1_0.gguf`, seen live: a model
# name can begin with Q and carry a digit exactly as a quant name does.
_QUANT = re.compile(
    r"(?:^|[-_.])((?:I?Q\d(?:_[A-Z0-9]+)*|TQ\d_\d|BF16|F16|F32))(?=$|[-_.])",
    re.IGNORECASE,
)


def _quantization(path: str) -> str:
    """The quant name out of a filename, which is where uploaders put it.

    The last match wins, because the quant is conventionally the final token and
    a repo name can contain something shaped like one.
    """
    stem = path.rsplit("/", 1)[-1].removesuffix(".gguf")
    matches = _QUANT.findall(stem)
    return matches[-1].upper() if matches else "unknown"
