"""Slice the parser_compare raw.jsonl for the n=171 run.

Reports per-arm:
  * tokens & cost stats (input/output mean, $/Q distribution)
  * failures (status != ok or empty raw_text)
  * answer_format breakdown (accuracy by str/int/float/list)

Plus surfsense agentic breakdown so we can compare apples to apples
even though the new_chat SSE doesn't surface per-call token counts.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "data" / "multimodal_doc" / "runs" / "2026-05-14T00-53-19Z" / "parser_compare"
RAW = RUN_DIR / "raw.jsonl"
ARTIFACT = RUN_DIR / "run_artifact.json"


def main() -> None:
    rows = [json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"raw rows: {len(rows)}")

    by_qid: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_qid[row["qid"]].append(row)
    print(f"unique questions: {len(by_qid)}")

    arm_metrics: dict[str, dict] = defaultdict(lambda: {
        "n": 0, "n_correct": 0, "n_failed": 0, "n_empty": 0,
        "costs": [], "in_tokens": [], "out_tokens": [], "latency_ms": [],
        "by_format": defaultdict(lambda: {"n": 0, "correct": 0}),
    })

    for row in rows:
        arm = row["arm"]
        m = arm_metrics[arm]
        m["n"] += 1
        graded = row.get("graded") or {}
        if graded.get("correct"):
            m["n_correct"] += 1

        err = row.get("error")
        raw_text = row.get("raw_text") or ""
        if err:
            m["n_failed"] += 1
        elif not raw_text.strip():
            m["n_empty"] += 1

        cost = row.get("cost_usd")
        if cost is not None:
            m["costs"].append(float(cost))
        ut = row.get("usage") or {}
        if ut.get("prompt_tokens"):
            m["in_tokens"].append(ut["prompt_tokens"])
        if ut.get("completion_tokens"):
            m["out_tokens"].append(ut["completion_tokens"])
        if row.get("latency_ms"):
            m["latency_ms"].append(row["latency_ms"])

        fmt = row.get("answer_format") or "unknown"
        m["by_format"][fmt]["n"] += 1
        if graded.get("correct"):
            m["by_format"][fmt]["correct"] += 1

    print()
    print("=" * 100)
    print(f"{'arm':<25} {'n':>4} {'acc%':>6} {'F1%':>6} {'fail':>5} {'$ mean':>10} {'$ median':>10} {'in tok mean':>12} {'out tok mean':>12} {'p50 ms':>8}")
    print("=" * 100)
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    per_arm_art = art["metrics"]["per_arm"]
    for arm, m in sorted(arm_metrics.items()):
        acc = m["n_correct"] / m["n"] * 100
        fail = m["n_failed"]
        cost_mean = statistics.mean(m["costs"]) if m["costs"] else 0.0
        cost_med = statistics.median(m["costs"]) if m["costs"] else 0.0
        in_mean = statistics.mean(m["in_tokens"]) if m["in_tokens"] else 0
        out_mean = statistics.mean(m["out_tokens"]) if m["out_tokens"] else 0
        lat_p50 = statistics.median(m["latency_ms"]) if m["latency_ms"] else 0
        f1 = per_arm_art.get(arm, {}).get("f1_mean", 0.0) * 100
        print(
            f"{arm:<25} {m['n']:>4} {acc:>5.1f}% {f1:>5.1f}% {fail:>5} "
            f"${cost_mean:>9.4f} ${cost_med:>9.4f} {in_mean:>12.0f} {out_mean:>12.0f} {lat_p50:>8.0f}"
        )

    print()
    print("by answer_format (accuracy):")
    formats = sorted({f for m in arm_metrics.values() for f in m["by_format"]})
    header = f"{'arm':<25} " + " ".join(f"{f:>10}" for f in formats)
    print(header)
    print("-" * len(header))
    for arm, m in sorted(arm_metrics.items()):
        cells = []
        for f in formats:
            row = m["by_format"][f]
            if row["n"] == 0:
                cells.append(f"{'-':>10}")
            else:
                pct = row["correct"] / row["n"] * 100
                cells.append(f"{pct:>5.0f}% ({row['correct']:>2}/{row['n']:>2})")
        print(f"{arm:<25} " + " ".join(cells))

    print()
    print("=" * 100)
    print("Aggregated cost (from run_artifact.json):")
    for arm, row in per_arm_art.items():
        print(
            f"  {arm:<25}  acc={row['accuracy']*100:5.1f}% "
            f"  $/Q LLM={row['llm_cost_per_q']:.4f}  "
            f"  preprocess total=${row['preprocess_cost_total']:.2f}  "
            f"  $/Q total={row['total_cost_per_q']:.4f}"
        )


if __name__ == "__main__":
    main()
