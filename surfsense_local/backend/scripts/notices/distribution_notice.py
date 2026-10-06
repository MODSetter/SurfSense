"""One notice per installed distribution: its version, licence id and licence text."""

import re
from collections.abc import Callable, Iterable
from importlib.metadata import Distribution, PackageNotFoundError, PackagePath
from pathlib import PurePath

_LICENCE_FILE = re.compile(r"^(licen[cs]e|copying|notice|unlicense)([-_.].*)?$", re.I)
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


def _licence_files(dist: Distribution) -> list[str]:
    """Licence files in the dist-info, which PEP 639 names, else anywhere installed."""
    files = [p for p in dist.files or [] if not p.name.endswith(".py")]
    declared = {PurePath(n).name for n in dist.metadata.get_all("License-File") or []}

    def licence(p: PackagePath) -> bool:
        return p.name in declared or bool(_LICENCE_FILE.match(p.name))

    in_info = [p for p in files if p.parts[0].endswith(".dist-info") and licence(p)]
    chosen = in_info or [p for p in files if licence(p)]
    texts: list[str] = []
    for path in sorted(chosen, key=lambda p: (len(p.parts), str(p))):
        try:
            text = _decoded(path)
        except OSError:
            continue
        if text and text not in texts:
            texts.append(text)
    return texts


def _licence_text(dist: Distribution) -> str:
    if texts := _licence_files(dist):
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
                "note": note,
            }
        )
    return entries
