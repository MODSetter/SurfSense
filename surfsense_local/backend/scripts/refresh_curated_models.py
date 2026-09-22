"""Rewrite `curated-models.json` from real headers and listings.

Run by hand, **never in CI**. The manifest is source: a person runs this, reads
what it proposes, downloads the file, chats with it, sets `validated`, and
commits. Four or five times a year.

    uv run scripts/refresh_curated_models.py

Everything mechanical is derived here. The three judgement fields stay in
`ENTRIES` below, where a person edits them:

  rank        preference order for *this app's job*, answering from the user's
              documents with citations that resolve. Not general capability.
              A person sets it by hand; nothing derives it.
  rank_basis  what produced the number, so a manifest part way through a
              migration is detectable and two scales are never mixed.
  validated   somebody ran this exact file.
"""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import httpx
from curated.huggingface import find_variant, read_header
from curated.projector import find_projector
from curated.tensor_bytes import decode_fraction

from modules.llm.catalog import SCHEMA_VERSION, CuratedModelsManifest
from modules.llm.fit import ModelShape
from modules.llm.gguf import to_shape

OUT = Path(__file__).resolve().parents[1] / "modules/llm/catalog/curated-models.json"
RANK_BASIS = "llmfit-1.1.11"

# The shipped ladder. Six rungs, one family, every machine gets a pick.
#
# The two Qwen2.5-Coder entries that were here are gone: SurfSense has no coding
# job. Chat is document Q&A with citations and the Studio formats are summary,
# flashcards, mindmap, quiz, podcast, office, web and visuals. A coder was
# taking two of eight slots in a list whose real gaps are a rung for 48 to 64 GB
# machines and a vision entry. Anyone who wants one searches for it.
ENTRIES = [
    # model_id, family, label, params, repo, quantization, rank
    ("Qwen/Qwen3-0.6B", "Qwen3", "Qwen3 0.6B", "0.6B", "unsloth/Qwen3-0.6B-GGUF", "Q4_K_M", 33),
    ("Qwen/Qwen3-1.7B", "Qwen3", "Qwen3 1.7B", "1.7B", "unsloth/Qwen3-1.7B-GGUF", "Q4_K_M", 48),
    ("Qwen/Qwen3-4B", "Qwen3", "Qwen3 4B", "4B", "unsloth/Qwen3-4B-GGUF", "Q4_K_M", 63),
    ("Qwen/Qwen3-8B", "Qwen3", "Qwen3 8B", "8B", "unsloth/Qwen3-8B-GGUF", "Q4_K_M", 78),
    ("Qwen/Qwen3-14B", "Qwen3", "Qwen3 14B", "14B", "unsloth/Qwen3-14B-GGUF", "Q4_K_M", 85),
    ("Qwen/Qwen3-32B", "Qwen3", "Qwen3 32B", "32B", "unsloth/Qwen3-32B-GGUF", "Q4_K_M", 92),
]

# Files somebody has downloaded, run, and confirmed citations resolve on.
VALIDATED: set[str] = set()


def _shape_fields(shape: ModelShape) -> dict:
    """Every field the estimator reads, taken from the dataclass itself.

    Listing them by hand here is what dropped two of them last time, and a
    dropped width prices the compute buffer as though the model had no layers.
    """
    fields = asdict(shape)
    # JSON has no tuples.
    fields["sliding_window_layers"] = list(fields["sliding_window_layers"])
    return fields


async def build() -> dict:
    models = []
    with httpx.Client(follow_redirects=True) as client:
        for model_id, family, label, params, repo, quant, rank in ENTRIES:
            file, size = find_variant(client, repo, quant)
            header = await read_header(repo, file)
            shape = to_shape(header)
            projector = find_projector(client, repo)
            fraction = decode_fraction(header, shape.expert_used_count, shape.expert_count)
            print(
                f"  {label:12s} {file:34s} {size / 1e9:5.2f} GB  "
                f"{shape.block_count} blocks, {shape.head_count_kv} kv-heads, "
                f"ctx {shape.context_length}, reads {fraction:.2f} per token"
                + (f", projector {projector[0]}" if projector else "")
            )
            models.append(
                {
                    "model_id": model_id,
                    "family": family,
                    "label": label,
                    "parameter_count": params,
                    "shape": _shape_fields(shape),
                    "capabilities": ["vision"] if projector else [],
                    "decode_fraction": fraction,
                    "variants": [
                        {
                            "repo": repo,
                            "file": file,
                            "quantization": quant,
                            "size_bytes": size,
                            "mmproj": projector[0] if projector else None,
                            "rank": rank,
                            "rank_basis": RANK_BASIS,
                            "validated": file in VALIDATED,
                        }
                    ],
                }
            )
    return {"schema_version": SCHEMA_VERSION, "models": models}


def main() -> None:
    print("reading headers over HTTP range, no weights downloaded:")
    manifest = asyncio.run(build())
    # Fail here rather than shipping something the app will reject at startup.
    CuratedModelsManifest.model_validate(manifest)
    OUT.write_text(json.dumps(manifest, indent=2) + "\n")
    unvalidated = [
        v["file"]
        for m in manifest["models"]
        for v in m["variants"]
        if not v["validated"]
    ]
    print(f"\nwrote {OUT.relative_to(Path.cwd())} ({len(manifest['models'])} entries)")
    if unvalidated:
        print(f"  {len(unvalidated)} builds are validated=false until someone runs them")


if __name__ == "__main__":
    main()
