"""What a revised copy's two downloads serve, and the names they are saved under.

"With changes" is the file without internal comments when it had any; "Clean"
is a Word version with every change accepted and no comments (03, decision 18).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.formats import revisable_format
from modules.artifacts.revised_copies.revision import CLEAN, EXTERNAL, revision_of
from modules.artifacts.revised_copies.versions import primary_path
from modules.artifacts.script_documents.version import version_of
from shared.config import get_storage_settings

Variant = Literal["changes", "clean"]

DEFAULT_SUFFIX: dict[Variant, str] = {"changes": "revised", "clean": "clean"}
# Windows refuses these as a file's stem, whatever follows.
_DEVICE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"{kind}{n}" for kind in ("COM", "LPT") for n in "123456789"]
)
_UNSAFE = re.compile(r'[<>:"/\|?*\x00-\x1f\x7f]')
NAME_BYTES = 255
SUFFIX_CHARS = 40


class DownloadUnavailableError(LookupError):
    """No such download for this artifact, in a sentence for the response."""


@dataclass(frozen=True)
class Download:
    path: Path
    filename: str
    mime: str


def revised_download(
    artifact: Artifact, variant: Variant, suffix: str | None = None
) -> Download:
    revision = revision_of(artifact.artifact_metadata)
    version = version_of(artifact.artifact_metadata)
    if revision is None or version is None:
        raise DownloadUnavailableError("artifact is not a revised copy")
    fmt = revisable_format(revision["source_name"])
    if fmt is None:
        raise DownloadUnavailableError("artifact is not a revised copy")
    if variant == "clean":
        path = _kept(revision.get(CLEAN))
        if path is None:
            raise DownloadUnavailableError("this version has no clean file")
    elif revision.get("internal_comment_ids"):
        # The primary holds the internal comments: only the external file may go.
        path = _kept(revision.get(EXTERNAL))
        if path is None:
            raise DownloadUnavailableError("the file is no longer on disk")
    else:
        path = primary_path(artifact)
        if path is None:
            raise DownloadUnavailableError("the file is no longer on disk")
    name = download_name(
        revision["source_name"], version.number, suffix or DEFAULT_SUFFIX[variant]
    )
    return Download(path, name, fmt.mime)


def download_name(source_name: str, number: int, suffix: str) -> str:
    """`<source stem> (<suffix> v<n>).<ext>`, safe on every OS and at most NAME_BYTES."""
    source = Path(source_name)
    stem = _safe(source.stem) or "document"
    if stem.split(".")[0].upper() in _DEVICE_NAMES:
        stem = f"_{stem}"
    tail = f" ({_safe(suffix)[:SUFFIX_CHARS] or 'revised'} v{number}){source.suffix}"
    while stem and len((stem + tail).encode()) > NAME_BYTES:
        stem = stem[:-1]
    return f"{stem.rstrip(' .') or 'document'}{tail}"


def _safe(text: str) -> str:
    return " ".join(_UNSAFE.sub("", text).split())


def _kept(record: object) -> Path | None:
    if not isinstance(record, dict):
        return None
    path = get_storage_settings().data_dir / record["storage_key"]
    return path if path.is_file() else None
