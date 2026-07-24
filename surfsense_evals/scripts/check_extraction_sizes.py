"""Sanity check extraction sizes against Sonnet 4.5's context window.

Sonnet 4.5 supports ~200k tokens. As a *very* rough heuristic, English
markdown is ~4 chars/token, so anything over ~750k chars likely won't
fit alongside the system + question + 512 max_output_tokens. Print
warnings for any extraction that's at risk.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAP = REPO / "data" / "multimodal_doc" / "maps" / "parser_compare_doc_map.jsonl"

CHARS_PER_TOKEN = 4
CTX_TOKENS = 200_000
PROMPT_OVERHEAD_TOKENS = 1_000  # system + question + format hint
MAX_OUTPUT_TOKENS = 512
SAFE_CHARS = (CTX_TOKENS - PROMPT_OVERHEAD_TOKENS - MAX_OUTPUT_TOKENS) * CHARS_PER_TOKEN


def main() -> None:
    rows = [
        json.loads(line) for line in MAP.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    total = len(rows)
    arm_max: dict[str, tuple[int, str]] = {}
    overflows: list[tuple[str, str, int]] = []
    for row in rows:
        for arm, ext in (row.get("extractions") or {}).items():
            chars = int(ext.get("chars") or 0)
            if arm not in arm_max or arm_max[arm][0] < chars:
                arm_max[arm] = (chars, row["doc_id"])
            if chars > SAFE_CHARS:
                overflows.append((row["doc_id"], arm, chars))

    print(f"PDFs in manifest: {total}")
    print(f"safe char budget: {SAFE_CHARS:,}  (~{(SAFE_CHARS // CHARS_PER_TOKEN):,} tokens)")
    print()
    print("largest extraction per arm:")
    for arm, (chars, doc_id) in sorted(arm_max.items()):
        print(f"  {arm:25s}  {chars:>10,} chars  ({doc_id})")

    print()
    if overflows:
        print(f"OVERFLOW RISK ({len(overflows)} extractions > safe budget):")
        for doc_id, arm, chars in overflows:
            est_tokens = chars // CHARS_PER_TOKEN
            print(f"  {doc_id} :: {arm} :: {chars:,} chars (~{est_tokens:,} tokens)")
    else:
        print("no overflow risk — all extractions fit Sonnet 4.5's 200k context.")


if __name__ == "__main__":
    main()
