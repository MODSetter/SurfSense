"""Check the install gate against the models people actually download.

    uv run scripts/audit_gate.py [--top 1000]

Run after a llama.cpp pin bump, or every few months. It answers the only
question that matters about a denylist, which is whether it is still right, and
it replaces a guard that the generated architecture table used to provide.

That table let a test hold every denylist key against the names llama.cpp
defines, which is how three misspellings were found: `granite-moe` for
`granitemoe`, `granite-hybrid` for `granitehybrid`, `nemotron-h` for
`nemotron_h`. Each had sat there refusing nothing, and nothing could tell.
With no table to compare against, a typo shows up here instead, as an entry
that matched no repo in the whole sample.

Two sections, and they fail differently:

    refusals        read them. A chat model in this list is a bug, and it is
                    the expensive kind because the user is told no and believes
                    it.
    dead entries    a name nothing matched. Usually harmless, sometimes a
                    misspelling. Check any that should plainly have matched.

Needs the network, so it is never part of the test suite.
"""

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.llm.catalog.local.classifier import GROUPS, classify

API = "https://huggingface.co/api/models"
PAGE = 100
PAUSE = 1.0


def listing(client: httpx.Client, wanted: int) -> list[str]:
    """The most downloaded GGUF repos, which is what search surfaces first."""
    names: list[str] = []
    for skip in range(0, wanted, PAGE):
        reply = client.get(
            API,
            params={
                "filter": "gguf",
                "sort": "downloads",
                "direction": -1,
                "limit": PAGE,
                "skip": skip,
            },
        )
        reply.raise_for_status()
        names += [row["id"] for row in reply.json()]
        time.sleep(PAUSE)
    return names


def facts(client: httpx.Client, repo: str) -> tuple[str, str | None] | None:
    """The repo summary search reads when a repo is opened."""
    try:
        reply = client.get(
            f"{API}/{repo}", params={"expand[]": ["gguf", "pipeline_tag"]}
        )
        reply.raise_for_status()
        payload = reply.json()
    except (httpx.HTTPError, ValueError):
        return None
    gguf = payload.get("gguf") or {}
    architecture = gguf.get("architecture")
    if not isinstance(architecture, str) or not architecture:
        return None
    tag = payload.get("pipeline_tag")
    return architecture.lower(), tag if isinstance(tag, str) else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=1000)
    options = parser.parse_args(argv)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        repos = listing(client, options.top)
        rows = []
        for repo in repos:
            found = facts(client, repo)
            if found is not None:
                rows.append((repo, *found))
            time.sleep(PAUSE)

    refused = [(r, a, t) for r, a, t in rows if classify(a, t).reason]
    matched = Counter()
    for _, architecture, tag in rows:
        for name in (architecture, tag):
            if name and name.lower() in GROUPS:
                matched[name.lower()] += 1

    print(f"listed {len(repos)}  parsed {len(rows)}  admitted {len(rows) - len(refused)}")
    print(f"\nREFUSED {len(refused)}. A chat model here is a bug.")
    for repo, architecture, tag in sorted(refused, key=lambda row: row[1]):
        print(f"  {architecture:<16} {tag!s:<22} {repo}")

    dead = sorted(set(GROUPS) - set(matched))
    print(f"\nDEAD ENTRIES {len(dead)} of {len(GROUPS)}. A misspelling looks like this.")
    print("  " + ", ".join(dead))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
