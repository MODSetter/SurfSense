"""Compute "intrinsic" accuracy by removing transient network errors.

A failure is *transient* if it's:
  * SSLError: SSL bad-record-mac (TLS hiccup)
  * Cloudflare 502 / 503 (provider-side load shedding)
  * empty_response with no error string and no other signal (likely
    connection reset mid-stream)
  * JSONDecodeError (parse error mid-stream)

A failure is *intrinsic* if it's a hard limit:
  * "exceeds .* limit" (size limits)
  * context_length errors
  * provider 400 with image / pdf decode failure
  * malformed-input failures

We re-compute accuracy with two denominators:
  * raw acc       = correct / 171  (what the headline reports)
  * adjusted acc  = correct / (171 - transient_failures)  (intrinsic)

Outputs a table that we can drop straight into the blog.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "data" / "multimodal_doc" / "runs" / "2026-05-14T00-53-19Z" / "parser_compare"
RAW = RUN / "raw.jsonl"


TRANSIENT_HINTS = (
    "sslv3_alert_bad_record_mac",
    "ssl_alert_bad_record_mac",
    "ssl: ssl",
    "cloudflare",
    "error 502",
    "error 503",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "jsondecodeerror",
)
INTRINSIC_HINTS = (
    "exceeds",
    "context_length",
    "context window",
    "could not process pdf",
    "could not process image",
)


def classify(error: str | None, raw_text: str) -> str:
    err = (error or "").lower()
    if not err and not raw_text.strip():
        return "transient_empty"
    if any(h in err for h in TRANSIENT_HINTS):
        return "transient_ssl_or_5xx"
    if any(h in err for h in INTRINSIC_HINTS):
        return "intrinsic_limit"
    if err:
        return "other_error"
    return "ok"


def main() -> None:
    rows = [
        json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    by_arm: dict[str, dict] = defaultdict(
        lambda: {
            "n": 0,
            "correct": 0,
            "transient_ssl_or_5xx": 0,
            "transient_empty": 0,
            "intrinsic_limit": 0,
            "other_error": 0,
        }
    )
    for row in rows:
        arm = row["arm"]
        m = by_arm[arm]
        m["n"] += 1
        graded = row.get("graded") or {}
        if graded.get("correct"):
            m["correct"] += 1
        kind = classify(row.get("error"), row.get("raw_text") or "")
        if kind != "ok":
            m[kind] += 1

    print(
        f"{'arm':<25} {'raw acc%':>8} {'transient':>10} {'intrinsic':>10} {'other':>6} {'adj acc% (no transient)':>22}"
    )
    print("-" * 88)
    for arm in sorted(by_arm):
        m = by_arm[arm]
        raw = m["correct"] / m["n"] * 100
        transient = m["transient_ssl_or_5xx"] + m["transient_empty"]
        intrinsic = m["intrinsic_limit"]
        other = m["other_error"]
        usable = m["n"] - transient
        adj = m["correct"] / usable * 100 if usable else 0
        print(f"{arm:<25} {raw:>7.1f}% {transient:>10} {intrinsic:>10} {other:>6} {adj:>21.1f}%")

    print()
    print("transient   = SSLError / 502 / 503 / empty stream / mid-stream JSON decode (would")
    print("              succeed on retry; eval harness has no built-in retry today).")
    print("intrinsic   = hard limit (e.g. >30MB Anthropic request, model context overflow).")
    print("adj acc%    = correct / (n - transient) — what the arm scores when network noise")
    print("              is removed; closest thing we have to a like-for-like quality number.")


if __name__ == "__main__":
    main()
