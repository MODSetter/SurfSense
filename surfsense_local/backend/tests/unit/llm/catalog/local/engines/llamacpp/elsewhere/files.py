"""Tiny GGUF files and other apps' model folders, built in a test's own tmp_path.

The files are written from the format spec (`tests/unit/llm/gguf/build.py`), not
by the reader under test, and every folder layout copies what each app writes:
nothing here touches a real home folder.
"""

import hashlib
import json
from pathlib import Path

from tests.unit.llm.gguf.build import (
    BOOL,
    STRING,
    UINT32,
    array,
    gguf,
    kv,
    tensor,
)

# llama.cpp's enum value for a mostly Q4_K_M file (`LlamaFileType.MOSTLY_Q4_K_M`).
Q4_K_M = 15


def chat_model_bytes(
    *,
    architecture: str = "qwen3",
    name: str | None = "Qwen3 8B",
    context: int = 40960,
    embedding: int = 4096,
    file_type: int | None = Q4_K_M,
    tensors: list[tuple[str, list[int]]] | None = None,
    split: tuple[int, int] | None = None,
) -> bytes:
    """A chat model's header: what llama.cpp's loader and our estimator read."""
    entries = [
        kv("general.architecture", STRING, architecture),
        kv(f"{architecture}.block_count", UINT32, 36),
        kv(f"{architecture}.context_length", UINT32, context),
        kv(f"{architecture}.embedding_length", UINT32, embedding),
        kv(f"{architecture}.attention.head_count", UINT32, 32),
        kv(f"{architecture}.attention.head_count_kv", UINT32, 8),
        kv(f"{architecture}.attention.key_length", UINT32, 128),
        kv(f"{architecture}.attention.value_length", UINT32, 128),
        kv("tokenizer.chat_template", STRING, "{{ messages }} <think>"),
        array("tokenizer.ggml.tokens", STRING, ["a", "b", "c"]),
    ]
    if name is not None:
        entries.insert(1, kv("general.name", STRING, name))
    if file_type is not None:
        entries.append(kv("general.file_type", UINT32, file_type))
    if split is not None:
        number, count = split
        entries += [
            kv("split.no", UINT32, number),
            kv("split.count", UINT32, count),
        ]
    rows = tensors if tensors is not None else [("token_embd.weight", [embedding, 3])]
    return gguf(entries, [tensor(n, dims) for n, dims in rows])


def write_chat_model(path: Path, **fields) -> Path:
    """Write a chat model's header to `path`, its folders included."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(chat_model_bytes(**fields))
    return path


def write_projector(path: Path, *, width: int = 4096) -> Path:
    """A vision projector, as every one measured on the hub declares itself."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        gguf(
            [
                kv("general.type", STRING, "mmproj"),
                kv("general.architecture", STRING, "clip"),
                kv("clip.has_vision_encoder", BOOL, True),
                kv("clip.vision.projection_dim", UINT32, width),
            ],
            [tensor("v.patch_embd.weight", [16, 16, 3, 1024])],
        )
    )
    return path


def write_embedder(path: Path) -> Path:
    """A sentence embedder, as Jan keeps beside its chat models."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        gguf(
            [
                kv("general.architecture", STRING, "bert"),
                kv("general.name", STRING, "all-MiniLM-L6-v2"),
                kv("bert.block_count", UINT32, 6),
                kv("bert.context_length", UINT32, 512),
                kv("bert.embedding_length", UINT32, 384),
                array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
            ],
            [tensor("token_embd.weight", [384, 2])],
        )
    )
    return path


def ollama_store(
    root: Path,
    name: str,
    tag: str,
    model: bytes,
    *,
    host: str = "registry.ollama.ai",
    namespace: str = "library",
    projector: bytes | None = None,
) -> tuple[Path, Path | None]:
    """An Ollama models folder: a manifest naming content-addressed blobs.

    The blob files are named `sha256-<hex>` of their bytes, with no extension,
    as Ollama writes them, so two tags of one model share a blob as they do there.
    """
    blobs = root / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    layers = []
    paths: list[Path | None] = []
    for media, content in (
        ("application/vnd.ollama.image.model", model),
        ("application/vnd.ollama.image.projector", projector),
    ):
        if content is None:
            paths.append(None)
            continue
        digest = hashlib.sha256(content).hexdigest()
        blob = blobs / f"sha256-{digest}"
        blob.write_bytes(content)
        layers.append(
            {"mediaType": media, "digest": f"sha256:{digest}", "size": len(content)}
        )
        paths.append(blob)
    layers.append(
        {
            "mediaType": "application/vnd.ollama.image.template",
            "digest": "sha256:" + "0" * 64,
            "size": 10,
        }
    )
    manifest = root / "manifests" / host / namespace / name / tag
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                "config": {"digest": "sha256:" + "1" * 64, "size": 10},
                "layers": layers,
            }
        )
    )
    model_path, projector_path = paths
    assert model_path is not None
    return model_path, projector_path
