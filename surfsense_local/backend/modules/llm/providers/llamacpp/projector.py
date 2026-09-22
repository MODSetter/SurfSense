"""Pairing a model on disk with the vision projector that belongs to it.

A vision model is two files. The weights answer questions and the projector
turns an image into something the weights can read, and llama.cpp loads the
second only when told to. The fitter does not count its memory either, so the
margin has to carry it.

Pairing only. What a file *is* comes from its header, in `gguf/file_kind.py`,
and `reprice` asks there before offering anything as a model. The name is still
how the pair is found, because that search globs a whole directory and a header
read per file is the cost this was always avoiding.
"""

from collections.abc import Iterable
from pathlib import Path

_MARKER = "mmproj"


def _named_as_projector(path: Path) -> bool:
    """Whether the name says projector, which is how the pair is found.

    Not a verdict on what the file is. `file_kind` answers that from the header,
    and `reprice` asks it before anything is offered as a model.
    """
    return _MARKER in path.stem.lower()


def projector_for(model_path: Path, named: Iterable[str] = ()) -> Path | None:
    """The projector belonging to `model_path`, or None for a text model.

    `named` is what the manifest says this model's projector is called, which is
    the exact answer for a curated entry. A searched model has no manifest row,
    so the fallback is the one projector sitting beside it. One, not the first of
    several: two projectors in a directory belong to two different models, and
    guessing between them would attach the wrong one.
    """
    directory = model_path.parent
    for name in named:
        candidate = directory / name
        if candidate.exists():
            return candidate

    beside = [path for path in sorted(directory.glob("*.gguf")) if _named_as_projector(path)]
    return beside[0] if len(beside) == 1 else None
