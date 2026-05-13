"""Quick sanity-check for the CRAG Task 3 doc map after ingest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    p = Path("data/research/maps/crag_t3_doc_map.jsonl")
    if not p.exists():
        print(f"Doc map missing: {p}")
        return 1
    rows = []
    settings = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "__settings__" in row:
            settings = row
            continue
        rows.append(row)
    print(f"Settings header: {settings}")
    print(f"Doc map rows:   {len(rows)}")
    for r in rows:
        print(f"  qid={r['qid']:<10} domain={r['domain']:<8} qtype={r['question_type']}")
        print(f"    question: {r['question'][:90]}")
        print(f"    gold:     {r['gold_answer'][:90]}")
        print(
            f"    pages:    {len(r['page_filenames'])} extracted, "
            f"{len(r['document_ids'])} doc_ids, "
            f"{len(r['missing_pages'])} missing"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
