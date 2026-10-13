"""Which files of a Hugging Face repo an embedder is downloaded as.

A generic int8 build first, which measured smaller and faster on a CPU than full
precision, then full precision; nothing tuned for one CPU, optimised for a GPU,
or in fp16, which runs slowly on a CPU. A bad quantisation is left to the probe
and the search check after the download.
"""

import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from modules.llm.catalog.local.listed_file import ListedFile

_PREFERENCE = (
    "onnx/model_int8.onnx",
    "onnx/model_quantized.onnx",
    "model_int8.onnx",
    "model_quantized.onnx",
    "onnx/model.onnx",
    "model.onnx",
)
TOKENIZER = "tokenizer.json"


class NotAnEmbedderCode(StrEnum):
    """Why an opened repo cannot be an embedder here.

    The sentence still travels with it, which the interface shows for a code it
    does not know. A row carries it where a `NotRunnableCode` goes, so the two
    never share a value. Keep in sync with `not-runnable-text.ts` in the
    frontend.
    """

    GATED = "repo_gated"
    NO_ONNX = "repo_no_onnx"
    NO_TOKENIZER = "repo_no_tokenizer"
    SCAN_FLAGGED = "repo_scan_flagged"


class NotRunnableError(Exception):
    """Why this repo cannot be an embedder here, in words the screen shows, and
    as a code when the sentence needs nothing but the code to be said again."""

    def __init__(self, reason: str, code: NotAnEmbedderCode | None = None) -> None:
        super().__init__(reason)
        self.code = code


@dataclass(frozen=True)
class PickedFiles:
    weights: ListedFile
    # The graph's external weights, which must land beside it under their names.
    data: tuple[ListedFile, ...]
    tokenizer: ListedFile

    @property
    def all(self) -> tuple[ListedFile, ...]:
        return (self.weights, *self.data, self.tokenizer)


def pick_files(listing: Iterable[ListedFile]) -> PickedFiles:
    files = {f.path: f for f in listing}
    weights = next((files[p] for p in _PREFERENCE if p in files), None)
    if weights is None:
        raise NotRunnableError(
            "This repo has no ONNX build SurfSense can run.", NotAnEmbedderCode.NO_ONNX
        )
    tokenizer = files.get(TOKENIZER)
    if tokenizer is None:
        raise NotRunnableError(
            "This repo has no tokenizer.json.", NotAnEmbedderCode.NO_TOKENIZER
        )
    data = tuple(
        f
        for path, f in sorted(files.items())
        if re.fullmatch(re.escape(weights.path) + r"(_data|\.data)(_\d+)?", path)
    )
    picked = PickedFiles(weights, data, tokenizer)
    if unhashed := [f.path for f in picked.all if not f.sha256]:
        # No code: the sentence names the file.
        raise NotRunnableError(f"Hugging Face lists no checksum for {unhashed[0]}.")
    return picked


def scan_verdict(status: Mapping[str, Any] | None, ours: Collection[str]) -> str | None:
    """Why Hugging Face's own scan refuses the repo, or None.

    Unsafe anywhere refuses it, and so does any flag on a file we would take.
    """
    for issue in (status or {}).get("filesWithIssues") or ():
        level = issue.get("level")
        if level == "safe":
            continue
        if level == "unsafe" or issue.get("path") in ours:
            return "Hugging Face's security scan flags this repo."
    return None
