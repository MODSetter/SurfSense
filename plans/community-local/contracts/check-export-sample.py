#!/usr/bin/env python3
"""Validate an unzipped contract-3 bundle against its manifest. Stdlib only.

    python3 check-export-sample.py [bundle_dir]

Exit 0 when the tree matches 03-export-bundle.md; prints every violation otherwise.
Both the exporter's tests and the importer's tests can point this at their output.
"""

import json
import sys
from pathlib import Path

FORMAT = "surfsense-export/1"
ROLES = {"user", "assistant"}
SKIP_REASONS = {"pending", "processing", "empty"}
OKF_FILES = {"index.md", "log.md"}


def safe_under(path: str, prefix: str) -> bool:
    return (
        path.startswith(prefix)
        and not path.startswith("/")
        and "\\" not in path
        and ".." not in path.split("/")
    )


def main(root: Path) -> int:
    errors: list[str] = []
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    if manifest.get("format") != FORMAT:
        errors.append(f"format is {manifest.get('format')!r}, expected {FORMAT!r}")

    listed: set[str] = set()
    seen_ids: set[int] = set()
    for ws in manifest.get("workspaces", []):
        prefix = f"workspaces/{ws['id']}/"
        docs_prefix = prefix + "documents/"

        chats = ws.get("chats")
        if chats != prefix + "chats.json":
            errors.append(f"workspace {ws['id']}: chats must be {prefix}chats.json, got {chats!r}")
        elif not (root / chats).is_file():
            errors.append(f"missing {chats}")
        else:
            for thread in json.loads((root / chats).read_text(encoding="utf-8")):
                for msg in thread.get("messages", []):
                    if msg.get("role") not in ROLES:
                        errors.append(f"thread {thread.get('id')}: bad role {msg.get('role')!r}")
                    if not all(set(c) == {"title"} for c in msg.get("citations", [])):
                        errors.append(f"thread {thread.get('id')}: citations must be [{{title}}]")

        for doc in ws.get("documents", []):
            path = doc["path"]
            if not safe_under(path, docs_prefix):
                errors.append(f"unsafe or misplaced path {path!r}")
            elif not (root / path).is_file():
                errors.append(f"missing {path}")
            if Path(path).name in OKF_FILES:
                errors.append(f"{path} is a reserved OKF filename")
            if doc["id"] in seen_ids:
                errors.append(f"duplicate document id {doc['id']}")
            seen_ids.add(doc["id"])
            listed.add(path)

        for skipped in ws.get("skipped", []):
            if skipped.get("reason") not in SKIP_REASONS:
                errors.append(f"skipped {skipped.get('id')}: bad reason {skipped.get('reason')!r}")

        docs_dir = root / docs_prefix
        if docs_dir.is_dir():
            for md in docs_dir.rglob("*.md"):
                rel = md.relative_to(root).as_posix()
                if md.name not in OKF_FILES and rel not in listed:
                    errors.append(f"{rel} exists but is not in the manifest")

    for err in errors:
        print(f"FAIL {err}")
    if not errors:
        print(f"ok: {len(seen_ids)} documents across {len(manifest['workspaces'])} workspaces")
    return 1 if errors else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "export-sample"
    sys.exit(main(target))
