"""The hand-authored part of an image model's entry.

Beyond what every entry names, a person reviews what the file cannot say: how
Studio should generate with it, which builds to pin, the files it runs with,
and the flags sd-server needs to run it here.
"""

from dataclasses import dataclass, field
from typing import Any

from local_manifest.entry import Entry


@dataclass(frozen=True)
class Companion:
    """A file a newer family runs with beside its weights, from its own repo:
    a VAE, a text encoder, or that encoder's vision projector."""

    role: str
    repo: str
    path: str
    # The vendor repo, when `repo` is a byte for byte copy of it.
    upstream_repo: str | None = None


@dataclass(frozen=True)
class ImageEntry(Entry):
    # `ImageDefaults` as the manifest writes it, with `origin` naming the source.
    image: dict[str, Any] = field(default_factory=dict)
    run_args: tuple[str, ...] = ()
    # The weights' builds in `repo` to pin, most preferred first: the first is
    # the default.
    builds: tuple[str, ...] = ("Q4_0",)
    # The folder of `repo` the builds sit in, where it holds more than one
    # conversion; the root by default.
    folder: str = ""
    # What every build runs with; SD 1 and XL carry theirs inside the one file.
    companions: tuple[Companion, ...] = ()


@dataclass(frozen=True)
class VideoEntry(ImageEntry):
    """An sd.cpp video model: the same files and builds as an image model's, and
    `VideoDefaults` as the manifest writes them in place of `image`."""

    video: dict[str, Any] = field(default_factory=dict)
