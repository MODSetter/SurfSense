"""Resolve a repo and quantization to an exact file, and read its header.

Authoring time only. The app never calls this: it reads the committed JSON.
"""

import httpx

from modules.llm.gguf import GgufHeader, header_from_url

API = "https://huggingface.co/api/models"
FILES = "https://huggingface.co/{repo}/resolve/main/{file}"


def find_variant(client: httpx.Client, repo: str, quantization: str) -> tuple[str, int]:
    """The one file in `repo` built at `quantization`, and its exact size.

    A repo holds roughly twenty builds, and repo plus quantization does not name
    one on its own: `Q4_K_M`, `UD-Q4_K_M` and a split set can all match. Split
    parts, projectors and draft models are excluded rather than guessed between.
    """
    reply = client.get(f"{API}/{repo}/tree/main", timeout=60)
    reply.raise_for_status()

    candidates = [
        row
        for row in reply.json()
        if row["path"].endswith(".gguf")
        and quantization.lower() in row["path"].lower()
        and "mmproj" not in row["path"].lower()
        and "draft" not in row["path"].lower()
        and "-of-" not in row["path"]
    ]
    if not candidates:
        raise SystemExit(f"{repo}: no single file build at {quantization}")
    # Prefer the shortest name: "Qwen3-8B-Q4_K_M" over "Qwen3-8B-UD-Q4_K_M".
    chosen = min(candidates, key=lambda row: len(row["path"]))
    return chosen["path"], chosen["size"]


async def read_header(repo: str, file: str) -> GgufHeader:
    """The header, over an HTTP range. No weights are downloaded.

    The whole header rather than the shape: the tensor table is what says how
    much of a mixture of experts is read per token.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        return await header_from_url(client, FILES.format(repo=repo, file=file))
