"""What is in the models folder, read from each file's own header.

Disk is the inventory: the runtime discovers the same folder. A file's header
says whether it is a model at all, so a projector, an imatrix or the second part
of a split build never shows as something to chat with. Reads are cached on path,
size and modification time, so a folder of large files is read once.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from modules.llm.catalog.local.classifier import Classification, classify
from modules.llm.catalog.local.engines.llamacpp.support import (
    projector_identifies_model,
    projector_reads_images,
)
from modules.llm.catalog.local.installs import InstalledBuild, projector_filename
from modules.llm.fit import ModelShape
from modules.llm.gguf import GgufHeader, header_from_file, to_shape
from modules.llm.gguf.file_kind import FileKind, kind_of

logger = logging.getLogger(__name__)

_SPLIT_NO = "split.no"
_PART = re.compile(r"^(?P<stem>.+)-(?P<part>\d{5})-of-(?P<total>\d{5})$")
_cache: dict[tuple[str, int, int], GgufHeader | None] = {}


@dataclass(frozen=True)
class DownloadedModel:
    model_id: str
    path: Path
    weights_bytes: int
    shape: ModelShape | None
    classification: Classification
    template: str | None
    record: InstalledBuild | None
    projector: Path | None
    projector_kv: dict[str, Any]
    model_kv: dict[str, Any]

    @property
    def projector_bytes(self) -> int:
        return self.projector.stat().st_size if self.projector else 0


class ProjectorNoticeKind(StrEnum):
    RENAME = "rename"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ProjectorNotice:
    kind: ProjectorNoticeKind
    projector: str
    model_id: str | None = None
    rename_to: str | None = None


def scan(
    models_dir: Path, installs: dict[str, InstalledBuild]
) -> list[DownloadedModel]:
    if not models_dir.exists():
        return []
    found = []
    for path in sorted(models_dir.glob("*.gguf")):
        header = read_cached(path)
        if header is not None and not _is_model(header):
            continue
        model_id = path.stem
        record = installs.get(model_id)
        projector = _projector_for(models_dir, model_id, record)
        projector_header = read_cached(projector) if projector else None
        meta = header.metadata if header else {}
        architecture = str(meta.get("general.architecture", ""))
        template = meta.get("tokenizer.chat_template")
        found.append(
            DownloadedModel(
                model_id=model_id,
                path=path,
                weights_bytes=_weights_bytes(models_dir, path, record),
                shape=to_shape(header) if header else None,
                classification=classify(architecture, readable=header is not None),
                template=template if isinstance(template, str) else None,
                record=record,
                projector=projector,
                projector_kv=dict(projector_header.metadata)
                if projector_header
                else {},
                model_kv=dict(meta),
            )
        )
    return found


def projector_notices(
    models_dir: Path, installed: list[DownloadedModel]
) -> tuple[ProjectorNotice, ...]:
    """Advice for visible projectors not paired by an install or exact name."""
    paired = {model.projector for model in installed if model.projector is not None}
    candidates = []
    for path in sorted(models_dir.glob("*.gguf")):
        if path in paired:
            continue
        header = read_cached(path)
        projector_kv = dict(header.metadata) if header else {}
        if not projector_reads_images(projector_kv):
            continue
        all_matches = tuple(
            model
            for model in installed
            if projector_identifies_model(projector_kv, model.model_kv)
        )
        matches = tuple(model for model in all_matches if model.projector is None)
        # A second projector for a model already paired is harmless and has no
        # useful rename target.
        if not matches and all_matches:
            continue
        candidates.append((path, matches))

    match_counts = Counter(
        model.model_id for _, matches in candidates for model in matches
    )
    notices = []
    for path, matches in candidates:
        unique = len(matches) == 1 and match_counts[matches[0].model_id] == 1
        if unique:
            model_id = matches[0].model_id
            notices.append(
                ProjectorNotice(
                    ProjectorNoticeKind.RENAME,
                    path.name,
                    model_id,
                    projector_filename(model_id),
                )
            )
        else:
            notices.append(
                ProjectorNotice(
                    ProjectorNoticeKind.NO_MATCH
                    if not matches
                    else ProjectorNoticeKind.AMBIGUOUS,
                    path.name,
                )
            )
    return tuple(notices)


def read_cached(path: Path) -> GgufHeader | None:
    """The file's header, or None when it cannot be read."""
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _cache:
        try:
            _cache[key] = header_from_file(path)
        except (OSError, ValueError):
            logger.warning("could not read the header of %s", path.name)
            _cache[key] = None
    return _cache[key]


def _is_model(header: GgufHeader) -> bool:
    kind = kind_of(header).kind
    if kind is FileKind.SHARD:
        return int(header.metadata.get(_SPLIT_NO, 0)) == 0
    return kind is FileKind.MODEL


def _projector_for(
    models_dir: Path, model_id: str, record: InstalledBuild | None
) -> Path | None:
    """The recorded projector, else one saved under this model's own name."""
    name = (
        record.projector
        if record and record.projector
        else projector_filename(model_id)
    )
    candidate = models_dir / name
    return candidate if candidate.exists() else None


def _weights_bytes(models_dir: Path, path: Path, record: InstalledBuild | None) -> int:
    """Every part of a split build, not only the one the runtime is pointed at."""
    if record is not None:
        names = record.weights
    elif match := _PART.match(path.stem):
        names = tuple(
            p.name
            for p in models_dir.glob(f"{match['stem']}-*-of-{match['total']}.gguf")
        )
    else:
        names = (path.name,)
    return sum(
        (models_dir / n).stat().st_size for n in names if (models_dir / n).exists()
    )
