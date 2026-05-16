"""Show questions where SurfSense was wrong but long-context was right (and vice versa)."""

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

    surf_wrong_lc_right = []
    lc_wrong_surf_right = []
    surf_wrong_bare_right = []
    for qid, arms in by_q.items():
        b = arms.get("bare_llm", {}).get("graded", {}).get("grade")
        lc = arms.get("long_context", {}).get("graded", {}).get("grade")
        s = arms.get("surfsense", {}).get("graded", {}).get("grade")
        if s == "incorrect" and lc == "correct":
            surf_wrong_lc_right.append(qid)
        if lc == "incorrect" and s == "correct":
            lc_wrong_surf_right.append(qid)
        if s == "incorrect" and b == "correct":
            surf_wrong_bare_right.append(qid)

    print(f"\nSurfSense INCORRECT but Long-Context CORRECT: {len(surf_wrong_lc_right)}")
    print(f"Long-Context INCORRECT but SurfSense CORRECT: {len(lc_wrong_surf_right)}")
    print(f"SurfSense INCORRECT but Bare CORRECT: {len(surf_wrong_bare_right)}")

    print("\n=== Where SurfSense is wrong but long-context is right (top 5) ===")
    for qid in surf_wrong_lc_right[:5]:
        arms = by_q[qid]
        b = arms.get("bare_llm", {})
        print(f"\n[{qid}] domain={b.get('domain')} qtype={b.get('question_type')}")
        print(f"  GOLD: {b.get('gold')!r}")
        for arm_name in ("bare_llm", "long_context", "surfsense"):
            a = arms.get(arm_name, {})
            t = (a.get("raw_text") or "").strip()
            tail = t[-180:] if t else ""
            grade = a.get("graded", {})
            print(f"  [{arm_name}] {grade.get('grade')} ({grade.get('method')}): {tail!r}")

    print("\n=== Where Long-Context is wrong but SurfSense is right (top 5) ===")
    for qid in lc_wrong_surf_right[:5]:
        arms = by_q[qid]
        b = arms.get("bare_llm", {})
        print(f"\n[{qid}] domain={b.get('domain')} qtype={b.get('question_type')}")
        print(f"  GOLD: {b.get('gold')!r}")
        for arm_name in ("bare_llm", "long_context", "surfsense"):
            a = arms.get(arm_name, {})
            t = (a.get("raw_text") or "").strip()
            tail = t[-180:] if t else ""
            grade = a.get("graded", {})
            print(f"  [{arm_name}] {grade.get('grade')} ({grade.get('method')}): {tail!r}")


if __name__ == "__main__":
    main()
