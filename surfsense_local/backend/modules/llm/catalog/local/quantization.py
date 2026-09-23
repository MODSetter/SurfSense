"""A build's quantization label, as the quantizer named it.

The one fact read from a filename. It has no other source: `UD-Q4_K_XL` is a
quantizer's convention, and the header's `general.file_type` names the same file
by its base type. The prefix is kept, because the preference order ranks
`UD-Q4_K_XL` above `Q4_K_M` and a label read without it would never match.
"""

import re

UNKNOWN = "unknown"

# A quant name, not merely something shaped like one: a model name can begin
# with Q and carry a digit exactly as a quant name does ("Qwen3").
_QUANT = re.compile(
    r"(?:^|[-_.])((?:UD[-_])?(?:I?Q\d(?:_[A-Z0-9]+)*|TQ\d_\d|MXFP4(?:_MOE)?|BF16|F16|F32))"
    r"(?=$|[-_.])",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"-\d{5}-of-\d{5}$", re.IGNORECASE)


def quantization_label(path: str) -> str:
    """The label from the basename, else from the nearest folder that names one.

    The last match in a name wins, because the quant is conventionally the final
    token and a repo name can hold something shaped like one.
    """
    *folders, basename = path.split("/")
    stem = _SPLIT.sub("", basename.removesuffix(".gguf"))
    for text in (stem, *reversed(folders)):
        if label := label_in(text):
            return label
    return UNKNOWN


def label_in(text: str) -> str:
    """The quant token in one path segment, or empty when it names none."""
    matches = _QUANT.findall(text)
    if not matches:
        return ""
    return matches[-1].upper().replace("UD_", "UD-")
