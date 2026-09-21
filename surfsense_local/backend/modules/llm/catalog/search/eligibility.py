"""What Hugging Face already knows about a repo's GGUF files.

The listing API parses the header of the first GGUF in a repo and serves the
result, which covers both eligibility questions without reading a byte of the
file: whether llama.cpp can run the architecture at all, and whether the model
carries a chat template.

Worth asking first because the alternative is a range request against a
multi-gigabyte file, and for an architecture llama.cpp cannot run that read
answers a question we had already decided.

It does not carry the KV shape, so it replaces nothing for a model we can run:
the header read still happens, it just no longer happens for models we cannot.
"""

from dataclasses import dataclass

import httpx

API = "https://huggingface.co/api/models"
TIMEOUT = httpx.Timeout(15.0, connect=10.0)


@dataclass(frozen=True)
class RepoFacts:
    """What the listing says about the first GGUF in a repo."""

    architecture: str
    context_length: int
    has_chat_template: bool


async def read_repo_facts(client: httpx.AsyncClient, repo: str) -> RepoFacts | None:
    """The parsed header Hugging Face already holds, or None when it holds none.

    None for a repo whose files it has not parsed, which is not a reason to
    refuse the repo: the caller falls through to reading the header itself.
    """
    try:
        reply = await client.get(
            f"{API}/{repo}", params={"expand[]": "gguf"}, timeout=TIMEOUT
        )
        reply.raise_for_status()
        payload = reply.json()
    except (httpx.HTTPError, ValueError):
        return None

    gguf = payload.get("gguf") if isinstance(payload, dict) else None
    if not isinstance(gguf, dict):
        return None

    architecture = gguf.get("architecture")
    if not isinstance(architecture, str) or not architecture:
        return None

    context = gguf.get("context_length")
    return RepoFacts(
        architecture=architecture,
        context_length=int(context) if isinstance(context, int) else 0,
        has_chat_template=bool(gguf.get("chat_template")),
    )
