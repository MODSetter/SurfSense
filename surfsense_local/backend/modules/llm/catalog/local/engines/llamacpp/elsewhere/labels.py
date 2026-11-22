"""What a found file is called on the screen, and what its header says about it.

A model is called what the person would recognise it by: an Ollama tag, else the
file's own name less its build (`Qwen3-8B-UD-Q4_K_XL.gguf` is Qwen3-8B), which is
how LM Studio and Hugging Face show it. Ollama's file names are content hashes
and Jan names every model `model.gguf`, so those are called by the header's
`general.name`, else by the folder. The header's name is a fallback rather than
the rule because converters fill it unevenly: measured, one SmolLM2 Instruct
file calls itself "Smollm2 135M 8k Lc100K Mix1 Ep2".

Everything else comes from the header: the tensor table counts the parameters,
`general.file_type` states the quantization where the name has no label, and
`<architecture>.context_length` the window.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from gguf.constants import Keys, LlamaFileType

from modules.llm.catalog.local.quantization import (
    UNKNOWN,
    label_in,
    quantization_label,
)
from modules.llm.gguf import GgufHeader

# Jan's name for every model file; its folder carries the model's id.
_GENERIC_STEM = "model"
# A content address, as Ollama and the hub's blob store name files.
_HASHED = re.compile(r"^(sha256[-:])?[0-9a-f]{32,}$", re.IGNORECASE)
_SPLIT = re.compile(r"-\d{5}-of-\d{5}$", re.IGNORECASE)


@dataclass(frozen=True)
class ModelLabel:
    name: str
    architecture: str
    # Counted from the tensor table; None when the header lists no tensors.
    parameters: int | None
    quantization: str
    # The window the model was trained for, as its header states it.
    context: int | None


def label_of(header: GgufHeader, path: Path, *, name: str | None = None) -> ModelLabel:
    """`name` is what the other app calls the model, when it calls it anything:
    an Ollama tag is what its user pulled and would look for."""
    meta = header.metadata
    architecture = str(meta.get(Keys.General.ARCHITECTURE) or "")
    context = meta.get(Keys.LLM.CONTEXT_LENGTH.format(arch=architecture))
    return ModelLabel(
        name=name
        or _own_name(path)
        or _header_name(meta)
        or path.parent.name
        or path.name,
        architecture=architecture,
        parameters=_parameters(header),
        quantization=_quantization(meta, path),
        context=int(context) if isinstance(context, int) else None,
    )


def _header_name(meta: dict) -> str:
    value = meta.get(Keys.General.NAME)
    return value.strip() if isinstance(value, str) else ""


def _own_name(path: Path) -> str:
    """The file's name less its build and split, or empty where the name says
    nothing about the model: a content hash, or Jan's `model.gguf`."""
    stem = _SPLIT.sub("", path.name.removesuffix(".gguf"))
    if stem.lower() == _GENERIC_STEM or _HASHED.match(stem):
        return ""
    if label := label_in(stem):
        # A label reads UD-; the file may write UD_.
        build = re.escape(label).replace(r"UD\-", "UD[-_]")
        trimmed = re.sub(rf"[-_.]{build}$", "", stem, flags=re.IGNORECASE)
        return trimmed or stem
    return stem


def _parameters(header: GgufHeader) -> int | None:
    if not header.tensors:
        return None
    return sum(math.prod(t.dims) for t in header.tensors)


def _quantization(meta: dict, path: Path) -> str:
    # The file, then the folder it sits in, as for a download.
    label = quantization_label(f"{path.parent.name}/{path.name}")
    if label != UNKNOWN:
        return label
    file_type = meta.get(Keys.General.FILE_TYPE)
    try:
        named = LlamaFileType(int(file_type)).name if file_type is not None else ""
    except ValueError:
        return UNKNOWN
    if not named or named == LlamaFileType.GUESSED.name:
        return UNKNOWN
    return named.removeprefix("MOSTLY_").removeprefix("ALL_")
