"""What a found file is called on the screen, from its own header.

Another app's file names are its own business: Ollama's are content hashes,
and Jan names every model `model.gguf`. The header names the model, its tensor
table counts the parameters, and `general.file_type` states the quantization.
The file name is read for one thing only, the quantizer's own label
(`UD-Q4_K_XL`), which no header holds, as the catalog does for a download.
"""

import math
from dataclasses import dataclass
from pathlib import Path

from gguf.constants import Keys, LlamaFileType

from modules.llm.catalog.local.quantization import UNKNOWN, quantization_label
from modules.llm.gguf import GgufHeader

# Jan's name for every model file; its folder carries the model's id.
_GENERIC_STEM = "model"


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
        name=name or _header_name(meta) or _file_name(path),
        architecture=architecture,
        parameters=_parameters(header),
        quantization=_quantization(meta, path),
        context=int(context) if isinstance(context, int) else None,
    )


def _header_name(meta: dict) -> str:
    value = meta.get(Keys.General.NAME)
    return value.strip() if isinstance(value, str) else ""


def _file_name(path: Path) -> str:
    stem = path.name.removesuffix(".gguf")
    if stem.lower() == _GENERIC_STEM and path.parent.name:
        return path.parent.name
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
