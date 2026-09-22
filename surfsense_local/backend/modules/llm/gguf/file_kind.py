"""What a GGUF says it is, read from the file rather than guessed from its name.

Three things used to answer this, all by guessing. `list_builds` matched
`"mmproj"`, `"draft"` and `"-of-"` in the path, `providers/llamacpp/projector.py`
matched `"mmproj"` again, and the install gate asked Hugging Face, which parses
one file per repo and publishes that as the repo's answer.

That last one is how 17 of the 1000 most downloaded repos are refused today.
`Jackrong/Qwen3.8-27B-MTP-GGUF` holds twelve builds of a Qwen 3.5 chat model
beside one vision sidecar. Hugging Face read the sidecar, called the repo `clip`,
and every build is hidden behind "This is the vision half of another model",
advice nobody can act on because the model it belongs to is that repo.

GGUF answers this itself. `general.type` is an official key with an official
enum in `gguf.constants.GGUFType`, and real files carry it: both projectors
measured on the hub report `general.type='mmproj'`.

**A truncated read means a model, and that is the useful half.** A projector,
an imatrix and a diffusion GGUF have no tokenizer, so their metadata ends within
a few kilobytes. A chat model's `tokenizer.ggml.tokens` runs to megabytes:
Qwen3 0.6B 5.93 MB, Llama 3.2 1B 7.82 MB, measured. So a small prefix parses for
everything this needs to recognise and cuts short for everything it should
admit, which makes the cheap read and the safe answer the same read.

Everything here fails open. A file that will not parse, a range request that
fails, a key that is missing: all `MODEL`. A refusal is never made from a
failure to read, because the runtime holds the real file and refuses there with
the same sentence if this was wrong.
"""

from dataclasses import dataclass
from enum import StrEnum

from gguf.constants import GGUFType, Keys

from modules.llm.gguf.header_prefix import GgufHeader, read_header_prefix

__all__ = ["PROBE_BYTES", "FileKind", "GgufFile", "file_kind", "kind_of"]

# Enough for every companion measured on the hub, and far short of any chat
# model's vocabulary. The asymmetry is the design, not a tuning choice.
PROBE_BYTES = 256 * 1024


class FileKind(StrEnum):
    MODEL = "model"
    PROJECTOR = "mmproj"
    ADAPTER = "adapter"
    IMATRIX = "imatrix"
    SHARD = "shard"


@dataclass(frozen=True)
class GgufFile:
    """What this file is, and what it is built as. Architecture is empty when
    the prefix could not be read, which is exactly when the kind is MODEL."""

    kind: FileKind
    architecture: str = ""


_BY_TYPE = {
    GGUFType.MMPROJ: FileKind.PROJECTOR,
    GGUFType.ADAPTER: FileKind.ADAPTER,
    GGUFType.IMATRIX: FileKind.IMATRIX,
    GGUFType.MODEL: FileKind.MODEL,
}

# Written by older writers that predate `general.type`, and by the patched
# stable-diffusion.cpp forks that never adopted it. Only ever consulted when the
# official key is absent.
_PROJECTOR_ARCHITECTURES = frozenset({"clip"})


def file_kind(prefix: bytes) -> GgufFile:
    """Read a prefix and say what the file is. Anything unreadable is a model."""
    try:
        header = read_header_prefix(prefix)
    except (ValueError, OSError):
        return GgufFile(FileKind.MODEL)
    return kind_of(header)


def kind_of(header: GgufHeader) -> GgufFile:
    """The same answer from a header already parsed, so a caller that needed
    the header anyway does not pay for a second read."""
    meta = header.metadata
    architecture = str(meta.get(Keys.General.ARCHITECTURE) or "")

    # A shard is a model split across files, so it is neither installable on its
    # own nor a companion. Checked first because a shard also says "model".
    if meta.get(Keys.Split.LLM_KV_SPLIT_COUNT):
        return GgufFile(FileKind.SHARD, architecture)

    declared = meta.get(Keys.General.TYPE)
    if isinstance(declared, str) and declared in _BY_TYPE:
        return GgufFile(_BY_TYPE[declared], architecture)

    if architecture.lower() in _PROJECTOR_ARCHITECTURES:
        return GgufFile(FileKind.PROJECTOR, architecture)
    return GgufFile(FileKind.MODEL, architecture)
