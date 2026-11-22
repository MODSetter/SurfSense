"""Whether the bundled llama.cpp can chat with a file another app downloaded.

The models folder fails open on what it cannot place, because a file there was
put there for SurfSense and the runtime refuses with its own words if the
guess was wrong. A file in another app's folder was not chosen for SurfSense,
and those apps run formats this runtime does not, so it is offered only on the
header's own evidence:

- it is a model, not a projector, adapter, imatrix or the second part of a split;
- the classifier makes it a chat model;
- its architecture is one llama.cpp's own table names. Ollama writes some under
  its own names (`gptoss`, `qwen25vl`, `mllama`), which this loader cannot build;
- it carries no projector tensors inside its weights. Ollama's multimodal files
  keep the vision tower in the model file, and llama.cpp's loader refuses a
  file holding tensors it did not create.
"""

from dataclasses import dataclass
from enum import StrEnum

from gguf.constants import MODEL_ARCH_NAMES, Keys

from modules.llm.catalog.local.classifier import UNSUPPORTED_REASON, classify
from modules.llm.gguf import GgufHeader
from modules.llm.gguf.file_kind import FileKind, kind_of
from modules.llm.model_type import ModelType

# The first segments llama.cpp gives a projector's tensors (vision, audio, and
# the projection between them and the model). No chat architecture in its
# table uses them, which a test holds against the pinned package.
COMPANION_TENSOR_PREFIXES = ("v.", "a.", "mm.")

_ARCHITECTURES = frozenset(MODEL_ARCH_NAMES.values())


class UnusableCode(StrEnum):
    """Why a found file is not offered, beside the classifier's own codes for
    a model that is not a chat model. Keep in sync with `elsewhere-text.ts`."""

    UNREADABLE = "unreadable"
    NOT_A_MODEL = "not_a_model"
    UNKNOWN_ARCHITECTURE = "unknown_architecture"
    VISION_INSIDE = "vision_inside"
    # The runtime's preset cannot carry the file's path (see `preset_can_name`).
    PATH = "path"
    # A split build whose other parts are not beside its first.
    MISSING_PARTS = "missing_parts"
    # A file or folder a person picked that is not there.
    NOT_FOUND = "not_found"
    # Picked from SurfSense's own models folder, which is already listed.
    IN_MODELS_FOLDER = "in_models_folder"


@dataclass(frozen=True)
class Unusable:
    """The sentence a person reads, and the code the interface words it by."""

    code: StrEnum
    reason: str


UNREADABLE = Unusable(UnusableCode.UNREADABLE, "SurfSense cannot read this file.")
NOT_A_MODEL = Unusable(
    UnusableCode.NOT_A_MODEL, "This file is part of a model, not a model on its own."
)
UNKNOWN_ARCHITECTURE = Unusable(
    UnusableCode.UNKNOWN_ARCHITECTURE,
    "This model is in a format SurfSense's runtime cannot load.",
)
VISION_INSIDE = Unusable(
    UnusableCode.VISION_INSIDE,
    "This file holds its image support inside the model, a format only the app "
    "that downloaded it can run.",
)
PATH = Unusable(
    UnusableCode.PATH,
    "SurfSense cannot open a file whose folder or name contains # or ;.",
)
MISSING_PARTS = Unusable(
    UnusableCode.MISSING_PARTS, "Some parts of this model are missing."
)
NOT_FOUND = Unusable(UnusableCode.NOT_FOUND, "Nothing is there any more.")
IN_MODELS_FOLDER = Unusable(
    UnusableCode.IN_MODELS_FOLDER,
    "This is SurfSense's own models folder, whose models are already listed.",
)


def unusable(header: GgufHeader | None) -> Unusable | None:
    """None when the bundled runtime can chat with this file."""
    if header is None:
        return UNREADABLE
    kind = kind_of(header)
    if kind.kind is FileKind.SHARD:
        if int(header.metadata.get(Keys.Split.LLM_KV_SPLIT_NO, 0)) != 0:
            return NOT_A_MODEL
    elif kind.kind is not FileKind.MODEL:
        return NOT_A_MODEL
    classification = classify(kind.architecture)
    if ModelType.TEXT_GEN not in classification.types:
        return Unusable(
            classification.code or UnusableCode.NOT_A_MODEL,
            classification.reason or UNSUPPORTED_REASON,
        )
    if kind.architecture not in _ARCHITECTURES:
        return UNKNOWN_ARCHITECTURE
    if any(t.name.startswith(COMPANION_TENSOR_PREFIXES) for t in header.tensors):
        return VISION_INSIDE
    return None
