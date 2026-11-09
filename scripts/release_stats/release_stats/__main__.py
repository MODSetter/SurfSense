"""Take a snapshot to a file, then optionally send it to PostHog.

    python -m release_stats snapshot --out release-stats.json
    python -m release_stats send release-stats.json

Two commands, so the workflow uploads the file before anything can fail to send.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .github_api import GitHubApi
from .posthog_capture import DEFAULT_HOST, send_batches
from .posthog_events import snapshot_events
from .snapshot import Snapshot, take_snapshot

_DEFAULT_REPO = "MODSetter/SurfSense"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release_stats")
    commands = parser.add_subparsers(dest="command", required=True)
    take = commands.add_parser("snapshot", help="read GitHub and write the JSON")
    take.add_argument("--out", required=True, type=Path)
    take.add_argument(
        "--repo", default=os.environ.get("GITHUB_REPOSITORY") or _DEFAULT_REPO
    )
    send = commands.add_parser("send", help="send a snapshot file to PostHog")
    send.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)

    if args.command == "snapshot":
        return _snapshot(args.out, args.repo)
    return _send(args.snapshot)


def _snapshot(out: Path, repo: str) -> int:
    # Traffic needs push access; RELEASE_STATS_TOKEN is the one that has it.
    token = os.environ.get("RELEASE_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    snapshot = take_snapshot(GitHubApi(token), repo, datetime.now(UTC))
    out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    _print_summary(snapshot)
    return 0


def _send(path: Path) -> int:
    api_key = os.environ.get("POSTHOG_PROJECT_API_KEY")
    if not api_key:
        print("POSTHOG_PROJECT_API_KEY is not set; nothing sent")
        return 0
    snapshot: Snapshot = json.loads(path.read_text(encoding="utf-8"))
    sent = send_batches(
        snapshot_events(snapshot),
        api_key=api_key,
        host=os.environ.get("POSTHOG_HOST") or DEFAULT_HOST,
    )
    print(f"sent {sent} events to PostHog")
    return 0


def _print_summary(snapshot: Snapshot) -> None:
    totals: Counter[str] = Counter()
    for row in snapshot["assets"]:
        totals[row["kind"]] += row["download_count"]
    releases = len({row["tag"] for row in snapshot["assets"]})
    print(f"{releases} releases, {len(snapshot['assets'])} assets")
    for kind, count in sorted(totals.items()):
        print(f"  {kind:<26} {count:>8}")
    if snapshot["traffic"] is None:
        notice = "::notice::" if os.environ.get("GITHUB_ACTIONS") else ""
        print(
            f"{notice}traffic skipped: {snapshot['traffic_skipped']}", file=sys.stderr
        )


if __name__ == "__main__":
    raise SystemExit(main())
