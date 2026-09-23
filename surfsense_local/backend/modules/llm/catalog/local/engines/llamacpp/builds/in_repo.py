"""Which files in a repo make a build.

One set of rules for the refresh script and for search, so a curated repo and a
searched one can never disagree about which file is the model and which is its
projector. It reads a listing only: names and sizes. What a file *is* is settled
later from its header, before any bytes move; this decides what to offer.
"""

import re
from collections.abc import Iterable

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.quantization import UNKNOWN, label_in, quantization_label

# Files that ship beside a model and are not one. Matched per path segment, so a
# drafter in an `MTP/` folder and one named `-draft-` are both caught.
_DRAFTER = re.compile(r"(?:^|[-_./])(mtp|draft|dflash|eagle3?)(?=$|[-_./])", re.I)
_BIG_ENDIAN = re.compile(r"(?:^|[-_.])(be|big[-_]?endian)$", re.I)
_SPLIT = re.compile(r"^(?P<stem>.+)-(?P<part>\d{5})-of-(?P<total>\d{5})\.gguf$", re.I)

# Highest fidelity first. A projector is small beside the weights, so the cost of
# the largest is a rounding error against the quality of what it feeds the model.
_PROJECTOR_PREFERENCE = ("F16", "BF16", "F32", "Q8_0")


def builds_in(
    listing: Iterable[ListedFile], *, repo: str = "", revision: str = "main"
) -> list[Build]:
    """Every build a repo offers, smallest first, each with its projector."""
    listing = list(listing)
    weights: list[ListedFile] = []
    for entry in listing:
        lowered = entry.path.lower()
        if not _companion_candidate(lowered) or "mmproj" in lowered.rsplit("/", 1)[-1]:
            continue
        basename = lowered.rsplit("/", 1)[-1]
        if not _BIG_ENDIAN.search(basename.removesuffix(".gguf")) and _in_build_folder(
            entry.path
        ):
            weights.append(entry)

    projector = preferred_projector(listing)
    builds: dict[str, Build] = {}
    for label, parts in _group_parts(weights):
        files = tuple(
            BuildFile(FileRole.WEIGHTS, p.path, p.size_bytes, p.sha256, repo, revision)
            for p in parts
        )
        if projector is not None:
            files += (
                BuildFile(
                    FileRole.PROJECTOR,
                    projector.path,
                    projector.size_bytes,
                    projector.sha256,
                    repo,
                    revision,
                ),
            )
        candidate = Build(label, files)
        current = builds.get(label)
        if current is None or _rank(candidate) < _rank(current):
            builds[label] = candidate
    return sorted(builds.values(), key=lambda b: (b.footprint_bytes, b.quantization))


def _in_build_folder(path: str) -> bool:
    """At the root, or inside folders that each name a quantization.

    Large builds live in `BF16/` or `Q8_0/`; any other folder (`distilled/`,
    `MTP/`) holds something that is not this repo's model.
    """
    return all(label_in(folder) for folder in path.split("/")[:-1])


def _group_parts(weights: list[ListedFile]) -> list[tuple[str, list[ListedFile]]]:
    """Single files as they are; split sets only when every part is listed."""
    singles: list[tuple[str, list[ListedFile]]] = []
    splits: dict[str, list[tuple[int, int, ListedFile]]] = {}
    for entry in weights:
        match = _SPLIT.match(entry.path)
        if match is None:
            singles.append((quantization_label(entry.path), [entry]))
            continue
        splits.setdefault(match["stem"], []).append(
            (int(match["part"]), int(match["total"]), entry)
        )
    for parts in splits.values():
        total = parts[0][1]
        numbers = sorted(number for number, _, _ in parts)
        if numbers != list(range(1, total + 1)):
            continue
        ordered = [entry for _, _, entry in sorted(parts, key=lambda p: p[0])]
        singles.append((quantization_label(ordered[0].path), ordered))
    return singles


def _rank(build: Build) -> tuple[int, int, int]:
    """Root before folder, a labelled file before an unlabelled one, then the
    shortest name, the way a quantizer's canonical file is usually named."""
    path = build.weights.path
    return (path.count("/"), build.quantization == UNKNOWN, len(path))


def preferred_projector(listing: Iterable[ListedFile]) -> ListedFile | None:
    """The repo's vision projector, judged by name alone, or None.

    The one rule the search list and a repo's builds share, so the two never
    disagree about whether a repo reads images. A name is a guess: the header
    read before install confirms it or drops the projector.
    """
    projectors = [
        entry
        for entry in listing
        if _companion_candidate(entry.path.lower())
        and "mmproj" in entry.path.lower().rsplit("/", 1)[-1]
    ]

    def rank(entry: ListedFile) -> tuple[int, int]:
        label = quantization_label(entry.path)
        position = (
            _PROJECTOR_PREFERENCE.index(label)
            if label in _PROJECTOR_PREFERENCE
            else len(_PROJECTOR_PREFERENCE)
        )
        return position, len(entry.path)

    return min(projectors, key=rank, default=None)


def _companion_candidate(lowered: str) -> bool:
    """A GGUF that is neither a drafter nor a calibration file."""
    return (
        lowered.endswith(".gguf")
        and not _DRAFTER.search(lowered)
        and "imatrix" not in lowered.rsplit("/", 1)[-1]
    )
