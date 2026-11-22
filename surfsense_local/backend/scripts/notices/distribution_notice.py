"""One notice per installed distribution: its version, licence id, licence text and NOTICE."""

import re
from collections.abc import Callable, Iterable
from importlib.metadata import Distribution, PackageNotFoundError, PackagePath
from pathlib import PurePath

_LICENCE_FILE = re.compile(r"^(licen[cs]es?|copying|unlicense)([-_.].*)?$", re.I)
# A NOTICE, or a third-party notices file such as onnxruntime's, carries others'
# attribution, not this package's terms, so it never passes the gate alone.
_NOTICE_FILE = re.compile(r"^(third[-_ ]?party[-_ ]?notices?|notice)([-_.].*)?$", re.I)
# A `License` field longer than this, or over several lines, is the text itself.
_ID_LENGTH = 80


def _licence_id(dist: Distribution) -> str:
    meta = dist.metadata
    if expression := meta.get("License-Expression"):
        return expression
    declared = (meta.get("License") or "").strip()
    short = "\n" not in declared and len(declared) <= _ID_LENGTH
    if declared and declared.upper() != "UNKNOWN" and short:
        return declared
    classifiers = [
        c.split(" :: ")[-1]
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    return " OR ".join(classifiers) or "UNKNOWN"


def _decoded(path: PackagePath) -> str:
    data = path.read_binary()
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError:
        # Older licence files are Latin-1, the copyright sign included.
        return data.decode("latin-1").strip()


def _dist_info_first(path: PackagePath) -> tuple[bool, int, str]:
    return (not path.parts[0].endswith(".dist-info"), len(path.parts), str(path))


def _texts(
    dist: Distribution, wanted: Callable[[PackagePath, set[str]], bool]
) -> list[str]:
    """Matching installed files: the dist-info's, which PEP 639 names, then the package's own."""
    files = [p for p in dist.files or [] if not p.name.endswith(".py")]
    declared = {PurePath(n).name for n in dist.metadata.get_all("License-File") or []}
    chosen = [p for p in files if wanted(p, declared)]
    texts: list[str] = []
    for path in sorted(chosen, key=_dist_info_first):
        try:
            text = _decoded(path)
        except OSError:
            continue
        if text and text not in texts:
            texts.append(text)
    return texts


def _is_notice(path: PackagePath, _declared: set[str]) -> bool:
    return bool(_NOTICE_FILE.match(path.name))


def _is_licence(path: PackagePath, declared: set[str]) -> bool:
    if _is_notice(path, declared):
        return False
    return path.name in declared or bool(_LICENCE_FILE.match(path.name))


def _licence_text(dist: Distribution) -> str:
    if texts := _texts(dist, _is_licence):
        return "\n\n".join(texts)
    declared = (dist.metadata.get("License") or "").strip()
    if "\n" in declared or len(declared) > _ID_LENGTH:
        return declared
    return ""


def python_notices(
    names: Iterable[str],
    find: Callable[[str], Distribution],
    notes: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    entries = []
    for name in names:
        note = (notes or {}).get(name, "")
        try:
            dist = find(name)
        except PackageNotFoundError:
            entries.append(
                {
                    "name": name,
                    "version": "",
                    "tree": "python",
                    "license": "UNKNOWN",
                    "text": "",
                    "notice": "",
                    "note": "Not installed where the notices were generated.",
                }
            )
            continue
        entries.append(
            {
                "name": dist.metadata["Name"] or name,
                "version": dist.version,
                "tree": "python",
                "license": _licence_id(dist),
                "text": _licence_text(dist),
                "notice": "\n\n".join(_texts(dist, _is_notice)),
                "note": note,
            }
        )
    return entries
