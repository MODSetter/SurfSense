"""Recompute per-arm accuracy/F1 after merging retry survivors into raw.jsonl.

Reads:
  - data/multimodal_doc/runs/<run_id>/parser_compare/raw.jsonl
  - data/multimodal_doc/runs/<run_id>/parser_compare/raw_retries.jsonl

For each (arm, qid) present in the retry artifact:
  - if the retry RECOVERED, the retry row replaces the original row (same
    grader is reused — see ``mmlongbench/grader.py``);
  - if the retry did NOT recover, the original row stays (still a failure,
    so ``correct=False`` and ``f1=0``).

Prints two tables side by side:
  * Raw run (no retries) — matches §1 of the blog.
  * Post-retry run        — final, "what would the headline have been if
                              the harness had had retries from day one".

It also writes ``data/multimodal_doc/runs/<run_id>/parser_compare/raw_post_retry.jsonl``
so any downstream notebook / report can join straight on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _row_key(row: dict) -> tuple[str, str]:
    return (str(row["arm"]), str(row["qid"]))


def _is_failure(row: dict) -> bool:
    if row.get("error"):
        return True
    return bool(not (row.get("raw_text") or "").strip())


def _summarise(rows_by_arm: dict[str, list[dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for arm, rows in rows_by_arm.items():
        n = len(rows)
        n_correct = sum(1 for r in rows if r.get("graded", {}).get("correct"))
        f1_sum = sum(float(r.get("graded", {}).get("f1") or 0.0) for r in rows)
        n_fail = sum(1 for r in rows if _is_failure(r))
        out[arm] = {
            "n": n,
            "n_correct": n_correct,
            "n_failures": n_fail,
            "accuracy": (n_correct / n) if n else 0.0,
            "f1_mean": (f1_sum / n) if n else 0.0,
            "failure_rate": (n_fail / n) if n else 0.0,
        }
    return out


def _print_table(title: str, summary: dict[str, dict]) -> None:
    print()
    print(title)
    print("-" * len(title))
    header = f"{'arm':<25} {'n':>4} {'n_corr':>7} {'acc':>7} {'F1':>7} {'fails':>6} {'fail%':>7}"
    print(header)
    print("-" * len(header))
    # stable order: highest accuracy first
    arms_sorted = sorted(summary.items(), key=lambda kv: -kv[1]["accuracy"])
    for arm, s in arms_sorted:
        print(f"{arm:<25} {s['n']:>4} {s['n_correct']:>7} "
              f"{s['accuracy']*100:>6.1f}% {s['f1_mean']*100:>6.1f}% "
              f"{s['n_failures']:>6} {s['failure_rate']*100:>6.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="2026-05-14T00-53-19Z")
    args = parser.parse_args()

    run_dir = REPO / "data" / "multimodal_doc" / "runs" / args.run_id / "parser_compare"
    raw_path = run_dir / "raw.jsonl"
    retry_path = run_dir / "raw_retries.jsonl"
    out_path = run_dir / "raw_post_retry.jsonl"

    if not raw_path.exists():
        print(f"raw.jsonl not found at {raw_path}", file=sys.stderr)
        return 1
    if not retry_path.exists():
        print(f"raw_retries.jsonl not found at {retry_path}", file=sys.stderr)
        return 1

    raw_rows = _read_jsonl(raw_path)
    retry_rows = _read_jsonl(retry_path)

    retry_by_key: dict[tuple[str, str], dict] = {
        _row_key(r): r for r in retry_rows
    }

    merged_rows: list[dict] = []
    n_replaced_recovered = 0
    n_replaced_still_failed = 0
    n_unchanged = 0
    for row in raw_rows:
        key = _row_key(row)
        retry = retry_by_key.get(key)
        if retry is None:
            merged_rows.append(row)
            n_unchanged += 1
            continue
        # The retry artifact carries a fresh ArmResult + grade in the same
        # shape, plus a "retry" sub-object. We use the retry row whenever
        # it represents a recovery; otherwise we keep the original (the
        # retry confirms it is intrinsic, but the original row is the one
        # the headline numbers were computed from, and the failure verdict
        # is identical either way).
        recovered = bool(retry.get("retry", {}).get("recovered"))
        if recovered:
            merged_rows.append(retry)
            n_replaced_recovered += 1
        else:
            merged_rows.append(row)
            n_replaced_still_failed += 1

    # Persist merged jsonl for downstream consumers
    with out_path.open("w", encoding="utf-8") as fh:
        for r in merged_rows:
            fh.write(json.dumps(r) + "\n")

    # Bucket per arm
    raw_by_arm: dict[str, list[dict]] = {}
    for r in raw_rows:
        raw_by_arm.setdefault(r["arm"], []).append(r)
    post_by_arm: dict[str, list[dict]] = {}
    for r in merged_rows:
        post_by_arm.setdefault(r["arm"], []).append(r)

    raw_summary = _summarise(raw_by_arm)
    post_summary = _summarise(post_by_arm)

    print()
    print(f"Run: {args.run_id}")
    print(f"Replaced (retry recovered):     {n_replaced_recovered}")
    print(f"Kept original (retry still failed): {n_replaced_still_failed}")
    print(f"Untouched rows:                 {n_unchanged}")
    print(f"Wrote merged artifact: {out_path.relative_to(REPO)}")

    _print_table("Raw run (no retries)", raw_summary)
    _print_table("Post-retry run (final)", post_summary)

    print()
    print("Delta (post-retry minus raw):")
    print(f"{'arm':<25} {'d_acc':>7} {'d_fails':>8}")
    print("-" * 42)
    for arm in sorted(set(raw_summary) | set(post_summary)):
        r = raw_summary.get(arm)
        p = post_summary.get(arm)
        if not r or not p:
            continue
        d_acc = (p["accuracy"] - r["accuracy"]) * 100
        d_fail = p["n_failures"] - r["n_failures"]
        print(f"{arm:<25} {d_acc:>+6.1f}p {d_fail:>+7d}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
