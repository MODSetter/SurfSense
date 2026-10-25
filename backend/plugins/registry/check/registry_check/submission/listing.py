"""An accepted submission written into the registry: its entry appended, its icon beside it."""

import json
from pathlib import Path

from registry_check.submission.submission_check import Submission


def list_submission(found: Submission, registry_path: Path) -> None:
    if found.entry is None:
        raise ValueError("a submission with problems is never listed")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["plugins"].append(found.entry)
    # The formatting the list is kept in, so the pull request's diff is the entry alone.
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    icon = found.entry.get("icon")
    if icon and found.icon is not None:
        (registry_path.parent / "icons" / icon).write_bytes(found.icon)
