"""A Hugging Face embedder's spec from the files its repo ships.

sentence-transformers states pooling, normalisation, prompts and length; a repo
without those files gets bge's defaults and is labelled inferred. The width here
is the config's; the probe after download has the last word.
"""

from dataclasses import dataclass
from typing import Any

from modules.embedding.huggingface.pick import PickedFiles
from modules.embedding.spec import EmbedderSpec, Identified, PinnedFile, Pooling, Source

# The ranking weight is measured per model; one not measured takes bge's.
UNMEASURED_WEIGHT = 0.65
# Passages are cut at 480 of bge's tokens; another tokenizer may count more,
# never four times as many, and a longer window only costs memory.
MAX_TOKENS_CAP = 2048
_POOLING = {
    "pooling_mode_cls_token": Pooling.CLS,
    "pooling_mode_mean_tokens": Pooling.MEAN,
    "pooling_mode_lasttoken": Pooling.LAST,
}


@dataclass(frozen=True)
class RepoConfig:
    """The repo's own files, each None where it ships none."""

    config: dict[str, Any] | None
    pooling: dict[str, Any] | None
    modules: list[dict[str, Any]] | None
    prompts: dict[str, str] | None
    max_seq_length: int | None


def spec_from_repo(
    repo: str,
    revision: str,
    picked: PickedFiles,
    found: RepoConfig,
    pipeline_tag: str | None,
) -> EmbedderSpec:
    del pipeline_tag  # the search admits only embedding tags; recorded for reading
    declared = found.pooling is not None or found.modules is not None
    prompts = found.prompts or {}
    config = found.config or {}
    length = found.max_seq_length or config.get("max_position_embeddings") or 512
    return EmbedderSpec(
        id=install_id(repo),
        source=Source.HUGGINGFACE,
        identified=Identified.DECLARED if declared else Identified.INFERRED,
        repo=repo,
        revision=revision,
        weights=PinnedFile(
            path=_name(picked.weights.path), sha256=picked.weights.sha256
        ),
        tokenizer=PinnedFile(
            path=_name(picked.tokenizer.path), sha256=picked.tokenizer.sha256
        ),
        dimension=int(config.get("hidden_size") or 384),
        pooling=next(
            (mode for key, mode in _POOLING.items() if (found.pooling or {}).get(key)),
            Pooling.CLS,
        ),
        # Search compares by cosine, so a unit vector loses nothing and keeps the
        # nearest-neighbour leg, which measures distance, in agreement with it.
        normalize=True,
        query_prefix=prompts.get("query", ""),
        document_prefix=prompts.get("document") or prompts.get("passage") or "",
        max_tokens=min(int(length), MAX_TOKENS_CAP),
        semantic_weight=UNMEASURED_WEIGHT,
    )


def install_id(repo: str) -> str:
    """What a Hugging Face pick is installed as: never a curated id."""
    return "hf--" + repo.replace("/", "--").lower()


def _name(path: str) -> str:
    return path.rsplit("/", 1)[-1]
