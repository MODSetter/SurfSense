"""The hand-authored part of an image model's entry.

Beyond what every entry names, a person reviews what the file cannot say: how
Studio should generate with it, and the flags sd-server needs to run it here.
"""

from dataclasses import dataclass, field
from typing import Any

from local_manifest.entry import Entry


@dataclass(frozen=True)
class ImageEntry(Entry):
    # `ImageDefaults` as the manifest writes it, with `origin` naming the source.
    image: dict[str, Any] = field(default_factory=dict)
    run_args: tuple[str, ...] = ()
