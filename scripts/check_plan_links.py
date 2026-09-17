"""Check relative markdown links and table shape in the community-local plans.

Run: python scripts/check_plan_links.py
Exit code is the number of problems found, so CI could gate on it.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def changed_plan_files() -> list[Path]:
    """Modified *and* untracked plans.

    `git diff --name-only` lists neither untracked files nor staged-only ones, so
    a brand-new plan would be skipped in silence. `status --porcelain` covers all
    three; its first two columns are the status code, and a rename reads
    `old -> new`, so take the right-hand side.
    """
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", "plans/community-local"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    names = (line[3:].split(" -> ")[-1].strip('"') for line in out.splitlines())
    return [ROOT / name for name in names if name.endswith(".md")]


def check_links(path: Path) -> list[str]:
    """Every relative link target must exist on disk."""
    problems = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                problems.append(f"{path.relative_to(ROOT)}:{lineno} dead link -> {target}")
    return problems


def check_tables(path: Path) -> list[str]:
    """Inside a table, every row needs the header's column count.

    A row is a table row only if the block started with a header + separator,
    which is what keeps prose containing a stray `|` from being scanned.
    """
    problems = []
    lines = path.read_text(encoding="utf-8").splitlines()
    fence = False
    width: int | None = None
    for lineno, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        stripped = line.strip()
        is_row = stripped.startswith("|") and stripped.endswith("|")
        if not is_row:
            width = None
            continue
        # Split on unescaped pipes only: `\|` is a literal pipe in a cell.
        cells = len(re.split(r"(?<!\\)\|", stripped)) - 2
        if width is None:
            width = cells
        elif cells != width:
            problems.append(
                f"{path.relative_to(ROOT)}:{lineno} table row has {cells} cells, header had {width}"
            )
    return problems


def main() -> int:
    files = changed_plan_files()
    problems = [p for f in files for p in check_links(f) + check_tables(f)]
    for problem in problems:
        print(problem)
    print(f"\nchecked {len(files)} changed plan files, {len(problems)} problems")
    return len(problems)


if __name__ == "__main__":
    sys.exit(main())
