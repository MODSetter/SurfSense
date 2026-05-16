"""Test the hypothesis: were the LC-arm errors actually context-window
overflow errors disguised as SSL / network failures?

If true, we'd expect:
  (a) literal "prompt is too long" / "context_length_exceeded" / "exceeds .* tokens" strings,
  (b) failures correlated with extraction size / input_tokens (large doc -> failure),
  (c) failing requests near or over Sonnet 4.5's 200k input-token limit.

If false (transport-layer hypothesis), we'd expect:
  (a) only SSL / 502 / empty stream / JSONDecode strings,
  (b) failures NOT correlated with size (uniform across PDFs by time, not by tokens),
  (c) failing requests well below the 200k limit.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "data" / "multimodal_doc" / "runs" / "2026-05-14T00-53-19Z" / "parser_compare"
RAW = RUN / "raw.jsonl"
MANIFEST = REPO / "data" / "multimodal_doc" / "maps" / "parser_compare_doc_map.jsonl"

CONTEXT_HINTS = (
    "context_length",
    "context window",
    "prompt is too long",
    "exceeds",
    "maximum context",
    "input tokens",
    "too many tokens",
    "over the maximum",
    "200000",
    "200_000",
)


def main() -> None:
    rows = [
        json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    extraction_size: dict[tuple[str, str], int] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = json.loads(line)
        for arm, ext in (m.get("extractions") or {}).items():
            extraction_size[(m["doc_id"], arm)] = int(ext.get("chars") or 0)

    print("=" * 80)
    print("(a) Literal 'context window' / 'prompt too long' error strings?")
    print("=" * 80)
    found = 0
    for row in rows:
        err = (row.get("error") or "").lower()
        if not err:
            continue
        for hint in CONTEXT_HINTS:
            if hint in err:
                print(f"  {row['arm']:<25} {row['qid']:<50}")
                print(f"      -> {err[:240]}")
                found += 1
                break
    if not found:
        print("  none found.")

    print()
    print("=" * 80)
    print("(b) Extraction size for OK vs FAILED rows per arm")
    print("=" * 80)
    arm_buckets: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"ok": [], "fail": []}
    )
    parser_arms = (
        "azure_basic_lc", "azure_premium_lc",
        "llamacloud_basic_lc", "llamacloud_premium_lc",
    )
    for row in rows:
        arm = row["arm"]
        if arm not in parser_arms:
            continue
        size = extraction_size.get((row["doc_id"], arm), 0)
        bucket = "fail" if (row.get("error") or not (row.get("raw_text") or "").strip()) else "ok"
        arm_buckets[arm][bucket].append(size)

    print(f"{'arm':<25} {'bucket':<5} {'n':>4} {'mean chars':>12} {'median':>10} {'max':>10}")
    for arm in parser_arms:
        for bucket in ("ok", "fail"):
            sizes = arm_buckets[arm][bucket]
            if not sizes:
                print(f"  {arm:<23} {bucket:<5} {0:>4}  -")
                continue
            print(
                f"  {arm:<23} {bucket:<5} {len(sizes):>4} "
                f"{statistics.mean(sizes):>12,.0f} "
                f"{statistics.median(sizes):>10,.0f} "
                f"{max(sizes):>10,}"
            )

    print()
    print("=" * 80)
    print("(c) Largest extraction each arm processed *successfully* vs *failed*")
    print("=" * 80)
    print(
        "(Sonnet 4.5 input limit ~200k tokens ~= 800k chars. If failures were "
        "context-overflow, max-OK would be near that cap. If max-OK is well "
        "above max-FAIL, the model handled bigger contexts than the failed "
        "ones, so size cannot be the cause.)"
    )
    print()
    for arm in parser_arms:
        ok_sizes = arm_buckets[arm]["ok"]
        fail_sizes = arm_buckets[arm]["fail"]
        if not ok_sizes:
            continue
        max_ok = max(ok_sizes)
        max_fail = max(fail_sizes) if fail_sizes else 0
        print(
            f"  {arm:<25} max OK = {max_ok:>10,} chars (~{max_ok / 4:>7,.0f} tokens)  "
            f"max FAIL = {max_fail:>10,} chars (~{max_fail / 4:>7,.0f} tokens)"
        )

    print()
    print("=" * 80)
    print("(d) Did the *known* overflow candidate fail?")
    print("=" * 80)
    print(
        "  3M_2018_10K x llamacloud_premium = 908,733 chars (~227k tokens) "
        "-- this is above Sonnet 4.5's 200k window."
    )
    print("  If transport hypothesis is correct, this should still fail with a "
          "real overflow error.")
    print("  If transport hypothesis is correct AND the model truncates silently, "
          "it might 'succeed' but be wrong.")
    print()
    for row in rows:
        if row["doc_id"] != "3M_2018_10K.pdf":
            continue
        if row["arm"] != "llamacloud_premium_lc":
            continue
        err = row.get("error") or "(none)"
        graded = row.get("graded") or {}
        print(
            f"  {row['qid']:<40} correct={graded.get('correct')!s:<5}  "
            f"err={err[:100]}"
        )


if __name__ == "__main__":
    main()
