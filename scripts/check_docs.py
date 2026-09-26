"""Check the markdown under docs/ and plans/: relative links resolve, tables keep
their shape, and every proposal declares a known status in its front matter.

Run: python scripts/check_docs.py [FILE ...]
With no arguments it checks every file. The pre-commit hook runs it that way on
purpose: deleting or renaming a file breaks links in docs nobody touched.
Exit code is 1 when anything is wrong.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_ROOTS = ("docs", "plans")
# The documents inside a contract fixture are sample data, not docs.
SKIP = ("docs/contracts/export-sample/",)
PROPOSALS = ROOT / "docs" / "proposals"
PROPOSAL_STATUSES = {"proposed", "accepted", "in-progress", "deferred", "withdrawn"}
# Markdown escapes a literal paren inside a link target as `\(`, so the target
# must be allowed to contain them and then unescaped before it hits the disk.
LINK = re.compile(r"\[[^\]]*\]\(((?:[^()\\]|\\.)+)\)")


def doc_files(args: list[str]) -> list[Path]:
    if args:
        paths = [(ROOT / arg).resolve() for arg in args]
    else:
        paths = sorted(p for root in DOC_ROOTS for p in (ROOT / root).rglob("*.md"))
    return [p for p in paths if p.suffix == ".md" and is_doc(p)]


def is_doc(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return rel.startswith(tuple(f"{root}/" for root in DOC_ROOTS)) and not rel.startswith(SKIP)


def link_base(path: Path) -> Path:
    """Where this file's relative links resolve from.

    Normally the file's own directory. `seo/drafts/` holds paste-ready copies of
    files that will live at the repo root — the README draft links `LICENSE` and
    `./surfsense_local` — so those resolve from ROOT or every one reads as dead.
    """
    return ROOT if path.parent.name == "drafts" else path.parent


def check_links(path: Path) -> list[str]:
    """Every relative link target outside a code fence must exist on disk."""
    base = link_base(path)
    problems = []
    fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            # Deliberate placeholders; 06-repo-readme.md wants them to fail
            # visibly in a browser, which is not this check's job.
            if "REPLACE-ME" in target:
                continue
            plain = re.sub(r"\\(.)", r"\1", target.split("#", 1)[0])
            if not (base / plain).resolve().exists():
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


def is_proposal(path: Path) -> bool:
    """A proposal is `proposals/<name>.md`, or `proposals/<name>/README.md`."""
    try:
        parts = path.relative_to(PROPOSALS).parts
    except ValueError:
        return False
    return (len(parts) == 1 and parts[0] != "README.md") or parts[1:] == ("README.md",)


def check_front_matter(path: Path) -> list[str]:
    """A proposal opens with front matter whose `status` is one we know."""
    if not is_proposal(path):
        return []
    where = f"{path.relative_to(ROOT)}:1"
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return [f"{where} proposal has no front matter"]
    header = lines[1 : lines.index("---", 1)]
    status = next(
        (line.split(":", 1)[1].strip() for line in header if line.startswith("status:")),
        None,
    )
    if status not in PROPOSAL_STATUSES:
        return [f"{where} proposal status {status!r} is not one of {sorted(PROPOSAL_STATUSES)}"]
    return []


def main(args: list[str]) -> int:
    files = doc_files(args)
    problems = [
        p for f in files for p in check_links(f) + check_tables(f) + check_front_matter(f)
    ]
    for problem in problems:
        print(problem)
    print(f"\nchecked {len(files)} doc files, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
