"""Inspect what the first 30 MMLongBench-Doc PDFs would look like for scoping.

Run from surfsense_evals/ root via:
    python scripts/inspect_first30.py

Prints which docs are already ingested (existing 5), which are new (25 to
upload), how many questions cover those 30 PDFs, and the answerable /
unanswerable + format mix.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def main() -> None:
    qpath = Path("data/multimodal_doc/mmlongbench/questions.jsonl")
    lines = qpath.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]

    docs_by_id = sorted({r["doc_id"] for r in rows})
    first30 = docs_by_id[:30]
    existing5 = {
        "05-03-18-political-release.pdf",
        "0b85477387a9d0cc33fca0f4becaa0e5.pdf",
        "0e94b4197b10096b1f4c699701570fbf.pdf",
        "11-21-16-Updated-Post-Election-Release.pdf",
        "12-15-15-ISIS-and-terrorism-release-final.pdf",
    }
    new25 = [d for d in first30 if d not in existing5]
    print(
        f"first 30 docs (alphabetical) — {len(new25)} new, "
        f"{len(first30) - len(new25)} already in SurfSense"
    )

    qs_in_30 = [r for r in rows if r["doc_id"] in set(first30)]
    fmts = Counter((r.get("answer_format") or "").lower() for r in qs_in_30)
    answerable = sum(v for k, v in fmts.items() if k != "none")
    unanswerable = fmts.get("none", 0)

    print(
        f"questions covering first 30 docs: total={len(qs_in_30)}  "
        f"answerable={answerable}  unanswerable={unanswerable}"
    )
    print(f"avg Qs/PDF: {len(qs_in_30) / 30:.1f}  answerable/PDF: {answerable / 30:.1f}")
    print(f"format mix in scope: {dict(fmts)}")
    print()
    print("25 new PDFs to ingest:")
    for d in new25:
        print(f"  - {d}")


if __name__ == "__main__":
    main()
