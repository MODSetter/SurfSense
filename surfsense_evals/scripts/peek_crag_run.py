"""Tiny helper to inspect the latest CRAG run's per-question outputs."""

from __future__ import annotations

import glob
import json
from collections import defaultdict


def main() -> None:
    raw_path = sorted(glob.glob("data/research/runs/*/crag/raw.jsonl"))[-1]
    print(f"Reading: {raw_path}")
    rows = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]
    by_q: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by_q[r["qid"]][r["arm"]] = r

    for qid, arms in list(by_q.items()):
        b = arms.get("bare_llm", {})
        l = arms.get("long_context", {})
        s = arms.get("surfsense", {})
        print(f"\n=== {qid} ({b.get('domain')}/{b.get('question_type')}) ===")
        print(f"  question: {b.get('extra', {}).get('question', '?')!r}")
        print(f"  gold: {b.get('gold')!r}")
        for arm_name, a in (("bare_llm", b), ("long_context", l), ("surfsense", s)):
            grade = a.get("graded", {})
            text = (a.get("raw_text") or "").strip()
            tail = text[-200:] if text else ""
            print(
                f"  [{arm_name}] grade={grade.get('grade')} "
                f"method={grade.get('method')}"
            )
            print(f"    -> {tail!r}")


if __name__ == "__main__":
    main()
