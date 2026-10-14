"""The hand-authored part of an audio model's entry.

Beyond what every entry names, a person reviews what neither the file nor the
server says: a voice model's voices, a recogniser's languages and locales, and
the memory each measured while it worked.
"""

from dataclasses import dataclass, field
from typing import Any

from local_manifest.entry import Entry


@dataclass(frozen=True)
class AudioEntry(Entry):
    # The model's folder in a repo that holds several models.
    folder: str = ""
    # The builds to pin, most preferred first: the first is the default.
    builds: tuple[str, ...] = ()
    # `AudioDefaults` as the manifest writes it, with `origin` naming the source.
    audio: dict[str, Any] = field(default_factory=dict)
    # `TranscriptionDefaults` likewise, for a recogniser in place of `audio`.
    transcription: dict[str, Any] = field(default_factory=dict)
