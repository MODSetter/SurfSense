"""The Hugging Face hub cache: `models--<org>--<repo>/snapshots/<commit>/`.

Each snapshot holds the files of one repo at one commit, symlinked into the
repo's `blobs/` where the system allows it and copied where it does not
(Windows without developer mode). The commit `refs/main` names is the one the
hub would hand back today, so only its files are offered; a repo with no ref
offers every snapshot, newest first, each file once.
"""

from pathlib import Path

from modules.llm.catalog.local.engines.llamacpp.elsewhere.candidate import Candidate
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import App
from modules.llm.catalog.local.engines.llamacpp.elsewhere.tree import in_tree

_PREFIX = "models--"
# A repo keeps its builds at the root and in folders named after a quantization.
_SNAPSHOT_DEPTH = 2


def in_hub_cache(root: Path, app: App = App.HUGGING_FACE) -> list[Candidate]:
    found: list[Candidate] = []
    for folder in _repos(root):
        repo = folder.name.removeprefix(_PREFIX).replace("--", "/")
        seen: set[str] = set()
        for snapshot in _snapshots(folder):
            for candidate in in_tree(snapshot, app, depth=_SNAPSHOT_DEPTH):
                relative = candidate.path.relative_to(snapshot).as_posix()
                if relative in seen:
                    continue
                seen.add(relative)
                found.append(
                    Candidate(
                        candidate.app,
                        candidate.path,
                        candidate.parts,
                        source=repo,
                        group=snapshot,
                        missing_parts=candidate.missing_parts,
                    )
                )
    return found


def _repos(root: Path) -> list[Path]:
    try:
        return sorted(
            p for p in root.iterdir() if p.name.startswith(_PREFIX) and p.is_dir()
        )
    except OSError:
        return []


def _snapshots(folder: Path) -> list[Path]:
    snapshots = folder / "snapshots"
    try:
        main = (folder / "refs" / "main").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        main = ""
    if main and (snapshots / main).is_dir():
        return [snapshots / main]
    try:
        every = [p for p in snapshots.iterdir() if p.is_dir()]
    except OSError:
        return []
    return sorted(every, key=_modified, reverse=True)


def _modified(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0
