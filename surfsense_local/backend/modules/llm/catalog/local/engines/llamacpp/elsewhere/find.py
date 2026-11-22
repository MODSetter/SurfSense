"""The chat models other apps downloaded, read from each file's own header.

Every place is read in its app's layout, then every file the same way: its
header says whether it is a model this runtime can chat with, what it is called,
how big it is, and what its window is. Nothing is written anywhere, and nothing
leaves the computer. A header is read once per process for a given path, size
and modification time, so asking again is a folder listing.

A projector goes with a model only on the other app's own evidence: Ollama's
manifest records it, and a folder holding one repo's files (a hub snapshot, an
LM Studio `publisher/repo` folder, a Jan model folder) gives its projector to
each build in it, as a searched repo does, once both headers state the same
width.
"""

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import (
    preferred_projector,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.candidate import Candidate
from modules.llm.catalog.local.engines.llamacpp.elsewhere.hub_cache import (
    in_hub_cache,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.labels import (
    ModelLabel,
    label_of,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.ollama import in_ollama
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import (
    App,
    Layout,
    Place,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.runs_here import (
    MISSING_PARTS,
    PATH,
    Unusable,
    UnusableCode,
    unusable,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.tree import in_tree
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import read_cached
from modules.llm.catalog.local.engines.llamacpp.support import (
    projector_fits_model,
    projector_identifies_model,
    projector_reads_images,
)
from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.fit import ModelShape
from modules.llm.gguf import GgufHeader, to_shape
from modules.llm.gguf.file_kind import FileKind, kind_of
from modules.llm.providers.llamacpp.preset import preset_can_name

logger = logging.getLogger(__name__)

# Said about on the screen: a file that is a model, but not one this runtime
# chats with. A companion file or one that will not parse is passed over.
_QUIET = frozenset({UnusableCode.UNREADABLE, UnusableCode.NOT_A_MODEL})
_APP_ORDER = {app: index for index, app in enumerate(App)}


@dataclass(frozen=True)
class FoundModel:
    app: App
    # The file the runtime opens: the first part of a split build.
    path: Path
    parts: tuple[Path, ...]
    projector: Path | None
    label: ModelLabel
    shape: ModelShape
    template: str | None
    model_kv: Mapping[str, Any]
    projector_kv: Mapping[str, Any]
    weights_bytes: int
    projector_bytes: int
    # What the other app says it is: an Ollama tag, or a repo.
    source: str | None


@dataclass(frozen=True)
class Skipped:
    """A model found and not offered, and why."""

    app: App
    path: Path
    name: str
    unusable: Unusable


@dataclass(frozen=True)
class Finding:
    models: tuple[FoundModel, ...] = ()
    skipped: tuple[Skipped, ...] = ()


def find_models(places: Sequence[Place], *, exclude: Sequence[Path] = ()) -> Finding:
    """`exclude` is SurfSense's own models folder, whose files are already listed."""
    excluded = [_resolved(path) for path in exclude]
    seen: set[Path] = set()
    models: list[FoundModel] = []
    skipped: list[Skipped] = []
    for place in places:
        candidates = _candidates(place)
        projectors = _projectors(candidates)
        for candidate in candidates:
            real = _resolved(candidate.path)
            if real in seen or any(real.is_relative_to(e) for e in excluded):
                continue
            seen.add(real)
            outcome = judge(candidate, projectors.get(candidate.group, []))
            if isinstance(outcome, FoundModel):
                models.append(outcome)
            elif outcome.unusable.code not in _QUIET:
                skipped.append(outcome)
    models.sort(key=lambda m: (_APP_ORDER[m.app], m.label.name.casefold(), str(m.path)))
    return Finding(tuple(models), tuple(skipped))


def find_file(path: Path, app: App = App.FOLDER) -> FoundModel | Skipped:
    """One file a person picked, judged as the scan judges one, with the
    projectors beside it. Any name will do: an Ollama blob has no extension."""
    candidates = in_tree(path.parent, app, depth=0)
    mine = next((c for c in candidates if path in c.parts), None)
    if mine is None:
        mine = Candidate(app, path, (path,), group=path.parent)
    return judge(mine, _projectors(candidates).get(mine.group, []))


def judge(
    candidate: Candidate, group_projectors: Sequence[tuple[Path, dict]] = ()
) -> FoundModel | Skipped:
    """One file: a model to offer, or why not."""
    header = header_of(candidate.path)
    problem = unusable(header)
    if problem is None and candidate.missing_parts:
        problem = MISSING_PARTS
    if problem is None and not preset_can_name(candidate.path):
        problem = PATH
    if problem is not None:
        name = (
            label_of(header, candidate.path, name=candidate.name).name
            if header is not None
            else candidate.name or candidate.path.name
        )
        return Skipped(candidate.app, candidate.path, name, problem)
    assert header is not None
    model_kv = dict(header.metadata)
    projector, projector_kv = _pair(candidate, model_kv, group_projectors)
    template = model_kv.get("tokenizer.chat_template")
    return FoundModel(
        app=candidate.app,
        path=candidate.path,
        parts=candidate.parts,
        projector=projector,
        label=label_of(header, candidate.path, name=candidate.name),
        shape=to_shape(header),
        template=template if isinstance(template, str) else None,
        model_kv=model_kv,
        projector_kv=projector_kv,
        weights_bytes=sum(_size(part) for part in candidate.parts),
        projector_bytes=_size(projector) if projector else 0,
        source=candidate.source,
    )


def header_of(path: Path) -> GgufHeader | None:
    """The header, or None for a file that will not parse.

    Broader than a read in the models folder: these files were written by other
    programs, and one that trips the parser in a way nobody anticipated must
    cost that file, not the whole scan.
    """
    try:
        return read_cached(path)
    except Exception:  # broad on purpose: see the docstring
        logger.warning("could not read the header of %s", path.name)
        return None


def _candidates(place: Place) -> list[Candidate]:
    try:
        if not place.root.is_dir():
            return []
        if place.layout is Layout.OLLAMA:
            return in_ollama(place.root)
        if place.layout is Layout.HUB_CACHE:
            return in_hub_cache(place.root, place.app)
        return in_tree(place.root, place.app, depth=place.depth)
    except OSError as error:
        # Another user's folder, a confined snap's hidden one, a drive gone.
        logger.info("could not read %s's models: %s", place.app.value, error)
        return []


def _projectors(candidates: Sequence[Candidate]) -> dict[Path | None, list]:
    """Per group, the files whose header says they are projectors that see."""
    found: dict[Path | None, list[tuple[Path, dict]]] = defaultdict(list)
    for candidate in candidates:
        if candidate.group is None:
            continue
        header = header_of(candidate.path)
        if header is None or kind_of(header).kind is not FileKind.PROJECTOR:
            continue
        kv = dict(header.metadata)
        if projector_reads_images(kv):
            found[candidate.group].append((candidate.path, kv))
    return found


def _pair(
    candidate: Candidate,
    model_kv: dict,
    group_projectors: Sequence[tuple[Path, dict]],
) -> tuple[Path | None, dict]:
    if candidate.projector is not None:
        # Recorded by the app that downloaded both, so a width it leaves out is
        # not held against the pair.
        header = header_of(candidate.projector)
        kv = dict(header.metadata) if header else {}
        if (
            projector_reads_images(kv)
            and projector_fits_model(kv, model_kv)
            and preset_can_name(candidate.projector)
        ):
            return candidate.projector, kv
        return None, {}
    matches = {
        path: kv
        for path, kv in group_projectors
        if projector_identifies_model(kv, model_kv) and preset_can_name(path)
    }
    if not matches:
        return None, {}
    chosen = preferred_projector(ListedFile(path.name, _size(path)) for path in matches)
    if chosen is not None:
        path = next(p for p in matches if p.name == chosen.path)
    elif len(matches) == 1:
        path = next(iter(matches))
    else:
        return None, {}
    return path, matches[path]


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _resolved(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()
