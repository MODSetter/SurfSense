"""Drill into the parser_compare n=171 raw.jsonl to surface every
failure, group by arm + PDF, and dump the underlying error strings so
we can write up a clean failure-mode taxonomy for the blog post.

Outputs (printed to stdout + written to `failures_n171.json`):
* per-arm failure count and rate
* per-PDF failure count across all arms (which docs are pathological?)
* error-string clusters per arm (so we can give human-readable causes)
* sample failure rows (one per cluster) for the appendix
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "data" / "multimodal_doc" / "runs" / "2026-05-14T00-53-19Z" / "parser_compare"
RAW = RUN / "raw.jsonl"
OUT = REPO / "scripts" / "failures_n171.json"


def _classify(error: str | None, raw_text: str) -> str:
    """Coarse-grained bucket for an error message."""

    blob = (error or "").lower()
    if not blob and not raw_text.strip():
        return "empty_response"
    if "rate limit" in blob or "429" in blob:
        return "rate_limit"
    if "context_length" in blob or "context window" in blob or "too many tokens" in blob:
        return "context_overflow"
    if "could not process image" in blob or "invalid image" in blob:
        return "image_decode_failure"
    if "could not process pdf" in blob or "invalid_request_error" in blob and "pdf" in blob:
        return "pdf_decode_failure"
    if "timeout" in blob or "timed out" in blob:
        return "timeout"
    if "5xx" in blob or "internal server error" in blob or "503" in blob or "502" in blob:
        return "provider_5xx"
    if "filenotfound" in blob:
        return "missing_extraction"
    if "badrequest" in blob:
        return "provider_400"
    if blob:
        return "other_error"
    return "unknown"


def main() -> None:
    rows = [
        json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    by_arm_failures: dict[str, list[dict]] = defaultdict(list)
    by_pdf_failures: dict[str, list[dict]] = defaultdict(list)
    error_clusters: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    n_per_arm: dict[str, int] = defaultdict(int)
    for row in rows:
        arm = row["arm"]
        n_per_arm[arm] += 1
        err = row.get("error")
        raw_text = row.get("raw_text") or ""
        if err or not raw_text.strip():
            cluster = _classify(err, raw_text)
            entry = {
                "qid": row["qid"],
                "doc_id": row["doc_id"],
                "answer_format": row["answer_format"],
                "gold": row["gold"],
                "error": err,
                "cluster": cluster,
                "raw_text_len": len(raw_text),
                "pages": row.get("pages"),
            }
            by_arm_failures[arm].append(entry)
            by_pdf_failures[row["doc_id"]].append({**entry, "arm": arm})
            error_clusters[arm][cluster].append(entry)

    print("=" * 90)
    print("Per-arm failure count & rate")
    print("=" * 90)
    print(f"{'arm':<25} {'n':>4} {'fail':>5} {'rate%':>6}")
    for arm in sorted(n_per_arm):
        f = len(by_arm_failures[arm])
        n = n_per_arm[arm]
        print(f"{arm:<25} {n:>4} {f:>5} {f / n * 100:>5.1f}%")

    print()
    print("=" * 90)
    print("Failure clusters per arm")
    print("=" * 90)
    for arm in sorted(error_clusters):
        print(f"\n{arm}:")
        for cluster, items in sorted(error_clusters[arm].items()):
            print(f"  {cluster:<22} {len(items):>3}")
            sample = items[0]
            err_short = (sample["error"] or "")[:200].replace("\n", " ")
            print(f"     example: {sample['qid']}  doc={sample['doc_id']} pages={sample['pages']}")
            print(f"     error: {err_short}")

    print()
    print("=" * 90)
    print("Per-PDF failure totals (PDFs with >=2 failures)")
    print("=" * 90)
    pdf_counts = Counter({pdf: len(rows) for pdf, rows in by_pdf_failures.items()})
    for pdf, count in pdf_counts.most_common():
        if count < 2:
            break
        arms_failed = sorted({r["arm"] for r in by_pdf_failures[pdf]})
        pages = by_pdf_failures[pdf][0].get("pages")
        print(f"  {pdf}  pages={pages}  failures={count}  arms={arms_failed}")

    print()
    print("=" * 90)
    print("All native_pdf failures (one row per failure)")
    print("=" * 90)
    for entry in by_arm_failures.get("native_pdf", []):
        err = (entry["error"] or "(no error string)")[:240].replace("\n", " ")
        print(
            f"  {entry['qid']}  doc={entry['doc_id']} pages={entry['pages']} cluster={entry['cluster']}"
        )
        print(f"    err: {err}")

    summary: dict[str, Any] = {
        "per_arm": {
            arm: {
                "n": n_per_arm[arm],
                "failures": len(by_arm_failures[arm]),
                "rate": len(by_arm_failures[arm]) / n_per_arm[arm],
                "clusters": {cluster: len(items) for cluster, items in error_clusters[arm].items()},
                "rows": by_arm_failures[arm],
            }
            for arm in sorted(n_per_arm)
        },
        "per_pdf": {
            pdf: [{**r, "arm": r["arm"]} for r in failures]
            for pdf, failures in by_pdf_failures.items()
        },
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote: {OUT}")


if __name__ == "__main__":
    main()
