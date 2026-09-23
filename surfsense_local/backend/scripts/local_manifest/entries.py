"""The hand-authored part of the local manifest: which models, in which order.

Position is preference, most preferred first. The recommendation walks this list
from the top and stars the first model with a build that runs well on the
machine, so the order means "good at this app's job" (answering from the user's
documents with citations that resolve), not general capability. Everything else
in the written manifest is read from the files.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    family: str
    publisher: str
    description: str
    license: str
    source_repo: str
    # Where the builds come from: an ungated mirror is preferred over a gated
    # vendor repo, with the vendor recorded as `upstream_repo`.
    repo: str
    upstream_repo: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


def _qwen3(size: str, description: str) -> Entry:
    return Entry(
        id=f"qwen3-{size.lower()}",
        name=f"Qwen3 {size}",
        family="Qwen3",
        publisher="Qwen",
        description=description,
        license="apache-2.0",
        source_repo=f"Qwen/Qwen3-{size}",
        repo=f"unsloth/Qwen3-{size}-GGUF",
        aliases=(
            f"Qwen/Qwen3-{size}",
            f"Qwen/Qwen3-{size}-GGUF",
            f"bartowski/Qwen_Qwen3-{size}-GGUF",
        ),
    )


ENTRIES: tuple[Entry, ...] = (
    _qwen3("32B", "The strongest answers here, for machines with 24 GB or more"),
    _qwen3("14B", "Careful answers from long documents, for 16 GB machines"),
    _qwen3("8B", "Balanced chat model for documents, fits most 12 GB machines"),
    _qwen3("4B", "Quick answers on 8 GB machines"),
    Entry(
        id="gemma-3-4b",
        name="Gemma 3 4B",
        family="Gemma 3",
        publisher="Google",
        description="Small chat model that also reads images, for 8 GB machines",
        license="gemma",
        # The vendor repo is gated and ships no GGUF; Unsloth's quantizations
        # are the ungated source of the builds.
        source_repo="google/gemma-3-4b-it",
        repo="unsloth/gemma-3-4b-it-GGUF",
        aliases=(
            "google/gemma-3-4b-it",
            "ggml-org/gemma-3-4b-it-GGUF",
            "bartowski/google_gemma-3-4b-it-GGUF",
        ),
    ),
    _qwen3("1.7B", "Light enough for older laptops"),
    _qwen3("0.6B", "The smallest that still answers, for any machine"),
)
