"""Pairing a model on disk with the vision projector that belongs to it.

A vision model is two files. The weights answer questions and the projector
turns an image into something the weights can read, and llama.cpp loads the
second only when told to. The fitter does not count its memory either, so the
margin has to carry it.

Both files sit in the models directory, so this is also what stops a projector
being offered as a model in its own right: it has a GGUF header and a size, and
nothing else about it says it cannot answer a question.
"""

from collections.abc import Iterable
from pathlib import Path

_MARKER = "mmproj"


def is_projector(path: Path) -> bool:
    """Whether this file is a projector rather than a model.

    Named by convention rather than read from the header: every publisher marks
    them this way, and the alternative is a header read per file on a path that
    runs at startup.
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

    beside = [path for path in sorted(directory.glob("*.gguf")) if is_projector(path)]
    return beside[0] if len(beside) == 1 else None
