"""Compute the deeper statistics the blog needs: McNemar pairwise tests,
per-PDF heterogeneity, latency/token distribution percentiles.

Reads the merged post-retry artifact:

    data/multimodal_doc/runs/<run_id>/parser_compare/raw_post_retry.jsonl

Outputs to stdout:

  1) Per-arm latency distribution (n, mean, std, p10, p25, p50, p75, p90, p95, p99, max).
  2) Per-arm input/output token distribution (mean, p50, p95, max).
  3) McNemar pairwise table: for every (arm_i, arm_j) ordered pair on the
     same 171 questions, count b_ij = #(arm_i correct & arm_j wrong) and
     b_ji = #(arm_i wrong & arm_j correct), and report the exact-binomial
     two-sided p-value. We include both raw (using the original raw.jsonl)
     and post-retry results.
  4) Per-PDF accuracy variance per arm (n_pdfs=30): mean, std, min, max.

Pure stdlib — no scipy/numpy.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (p in [0, 100])."""

    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(s[int(k)])
    return float(s[lo] + (s[hi] - s[lo]) * (k - lo))


# ---------------------------------------------------------------------------
# McNemar exact-binomial p-value
# ---------------------------------------------------------------------------


def _binom_coef(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def _mcnemar_exact_pvalue(b: int, c: int) -> float:
    """Two-sided exact-binomial McNemar p-value.

    Tests H0: P(arm_i wrong, arm_j right) == P(arm_i right, arm_j wrong)
    on discordant pairs only. Under H0 the count b ~ Bin(b+c, 0.5).
    The two-sided p-value is

        P(X <= min(b, c)) + P(X >= max(b, c))

    computed exactly (cheap because b+c <= 27 in our run).
    """

    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # Two-sided exact: 2 * P(X <= k) clipped at 1.0
    cdf = sum(_binom_coef(n, i) for i in range(k + 1))
    p = 2.0 * cdf / (2**n)
    return min(1.0, p)


def _mcnemar_table(rows: list[dict]) -> dict:
    """Group rows -> {qid: {arm: bool_correct}} and compute pairwise."""

    by_qid: dict[str, dict[str, bool]] = {}
    arms_seen: set[str] = set()
    for r in rows:
        qid = r["qid"]
        arm = r["arm"]
        graded = r.get("graded") or {}
        correct = bool(graded.get("correct"))
        by_qid.setdefault(qid, {})[arm] = correct
        arms_seen.add(arm)

    arms = sorted(arms_seen)
    qids = sorted(by_qid)
    out: dict[str, dict] = {"arms": arms, "n_qids": len(qids), "pairs": []}
    for i, ai in enumerate(arms):
        for aj in arms[i + 1 :]:
            b = c = both = neither = 0
            for q in qids:
                row = by_qid[q]
                if ai not in row or aj not in row:
                    continue
                ci, cj = row[ai], row[aj]
                if ci and not cj:
                    b += 1
                elif cj and not ci:
                    c += 1
                elif ci and cj:
                    both += 1
                else:
                    neither += 1
            p = _mcnemar_exact_pvalue(b, c)
            out["pairs"].append(
                {
                    "arm_i": ai,
                    "arm_j": aj,
                    "b_i_only": b,
                    "c_j_only": c,
                    "both_correct": both,
                    "both_wrong": neither,
                    "p_value": p,
                }
            )
    return out


# ---------------------------------------------------------------------------
# Per-PDF heterogeneity
# ---------------------------------------------------------------------------


def _per_pdf_stats(rows: list[dict]) -> dict[str, dict]:
    """For each arm, per-PDF accuracy = correct/total questions on that PDF."""

    bucket: dict[str, dict[str, list[bool]]] = {}
    for r in rows:
        arm = r["arm"]
        pdf = r["doc_id"]
        graded = r.get("graded") or {}
        bucket.setdefault(arm, {}).setdefault(pdf, []).append(bool(graded.get("correct")))

    out: dict[str, dict] = {}
    for arm, pdfs in bucket.items():
        accs = [sum(b) / len(b) for b in pdfs.values() if b]
        if not accs:
            continue
        out[arm] = {
            "n_pdfs": len(accs),
            "mean": statistics.mean(accs),
            "std": statistics.stdev(accs) if len(accs) > 1 else 0.0,
            "min": min(accs),
            "max": max(accs),
            "p25": _percentile(accs, 25),
            "p50": _percentile(accs, 50),
            "p75": _percentile(accs, 75),
            "n_pdfs_zero": sum(1 for a in accs if a == 0.0),
            "n_pdfs_perfect": sum(1 for a in accs if a == 1.0),
        }
    return out


# ---------------------------------------------------------------------------
# Latency / token distributions
# ---------------------------------------------------------------------------


def _per_arm_latency(rows: list[dict]) -> dict[str, dict]:
    by_arm: dict[str, list[float]] = {}
    for r in rows:
        lat = r.get("latency_ms")
        if lat is None or lat == 0:
            continue
        by_arm.setdefault(r["arm"], []).append(float(lat))
    out: dict[str, dict] = {}
    for arm, lats in by_arm.items():
        out[arm] = {
            "n": len(lats),
            "mean_s": statistics.mean(lats) / 1000,
            "std_s": (statistics.stdev(lats) / 1000) if len(lats) > 1 else 0.0,
            "p10_s": _percentile(lats, 10) / 1000,
            "p25_s": _percentile(lats, 25) / 1000,
            "p50_s": _percentile(lats, 50) / 1000,
            "p75_s": _percentile(lats, 75) / 1000,
            "p90_s": _percentile(lats, 90) / 1000,
            "p95_s": _percentile(lats, 95) / 1000,
            "p99_s": _percentile(lats, 99) / 1000,
            "max_s": max(lats) / 1000,
            # Coefficient of variation: std / mean (unitless tail-fatness).
            "cv": (
                statistics.stdev(lats) / statistics.mean(lats)
                if len(lats) > 1 and statistics.mean(lats) > 0
                else 0.0
            ),
        }
    return out


def _per_arm_tokens(rows: list[dict]) -> dict[str, dict]:
    by_arm_in: dict[str, list[float]] = {}
    by_arm_out: dict[str, list[float]] = {}
    for r in rows:
        t_in = r.get("input_tokens") or 0
        t_out = r.get("output_tokens") or 0
        if t_in:
            by_arm_in.setdefault(r["arm"], []).append(float(t_in))
        if t_out:
            by_arm_out.setdefault(r["arm"], []).append(float(t_out))
    out: dict[str, dict] = {}
    for arm in sorted(set(by_arm_in) | set(by_arm_out)):
        in_vals = by_arm_in.get(arm, [])
        out_vals = by_arm_out.get(arm, [])
        if not in_vals and not out_vals:
            continue
        entry: dict = {}
        if in_vals:
            entry["input"] = {
                "n": len(in_vals),
                "mean": statistics.mean(in_vals),
                "p50": _percentile(in_vals, 50),
                "p95": _percentile(in_vals, 95),
                "max": max(in_vals),
            }
        if out_vals:
            entry["output"] = {
                "n": len(out_vals),
                "mean": statistics.mean(out_vals),
                "p50": _percentile(out_vals, 50),
                "p95": _percentile(out_vals, 95),
                "max": max(out_vals),
            }
        out[arm] = entry
    return out


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------


def _print_latency(title: str, lat: dict[str, dict]) -> None:
    print()
    print(title)
    print("-" * len(title))
    header = (
        f"{'arm':<25} {'n':>4} {'mean':>7} {'std':>7} "
        f"{'p50':>7} {'p90':>7} {'p95':>7} {'p99':>7} {'max':>7} {'CV':>5}"
    )
    print(header)
    print("-" * len(header))
    for arm in sorted(lat, key=lambda a: lat[a]["mean_s"]):
        s = lat[arm]
        print(
            f"{arm:<25} {s['n']:>4} "
            f"{s['mean_s']:>6.1f}s {s['std_s']:>6.1f}s "
            f"{s['p50_s']:>6.1f}s {s['p90_s']:>6.1f}s {s['p95_s']:>6.1f}s "
            f"{s['p99_s']:>6.1f}s {s['max_s']:>6.1f}s {s['cv']:>5.2f}"
        )


def _print_tokens(title: str, toks: dict[str, dict]) -> None:
    print()
    print(title)
    print("-" * len(title))
    header = (
        f"{'arm':<25} {'in mean':>9} {'in p50':>9} {'in p95':>9} {'in max':>9}"
        f"  {'out mean':>9} {'out p95':>9}"
    )
    print(header)
    print("-" * len(header))
    for arm in sorted(toks):
        e = toks[arm]
        ein = e.get("input")
        eout = e.get("output")
        if not ein:
            continue
        print(
            f"{arm:<25} "
            f"{ein['mean']:>9,.0f} {ein['p50']:>9,.0f} {ein['p95']:>9,.0f} {ein['max']:>9,.0f}  "
            f"{(eout or {}).get('mean', 0):>9,.0f} {(eout or {}).get('p95', 0):>9,.0f}"
        )


def _print_pdf_var(title: str, var: dict[str, dict]) -> None:
    print()
    print(title)
    print("-" * len(title))
    header = (
        f"{'arm':<25} {'n_pdfs':>7} {'mean':>7} {'std':>7} {'min':>7} "
        f"{'p25':>7} {'p50':>7} {'p75':>7} {'max':>7} {'#0%':>5} {'#100%':>6}"
    )
    print(header)
    print("-" * len(header))
    for arm in sorted(var, key=lambda a: -var[a]["mean"]):
        s = var[arm]
        print(
            f"{arm:<25} {s['n_pdfs']:>7} "
            f"{s['mean'] * 100:>6.1f}% {s['std'] * 100:>6.1f}% {s['min'] * 100:>6.1f}% "
            f"{s['p25'] * 100:>6.1f}% {s['p50'] * 100:>6.1f}% {s['p75'] * 100:>6.1f}% "
            f"{s['max'] * 100:>6.1f}% {s['n_pdfs_zero']:>5} {s['n_pdfs_perfect']:>6}"
        )


def _print_mcnemar(title: str, table: dict) -> None:
    print()
    print(title)
    print("-" * len(title))
    print(f"n_qids on which all arms have a graded row: {table['n_qids']}")
    header = (
        f"{'arm_i':<25} {'arm_j':<25} {'b':>4} {'c':>4} "
        f"{'both ok':>8} {'both wr':>8} {'p (2-sided)':>13} {'sig':>4}"
    )
    print(header)
    print("-" * len(header))
    for pair in sorted(table["pairs"], key=lambda p: p["p_value"]):
        sig = ""
        if pair["p_value"] < 0.001:
            sig = "***"
        elif pair["p_value"] < 0.01:
            sig = "**"
        elif pair["p_value"] < 0.05:
            sig = "*"
        print(
            f"{pair['arm_i']:<25} {pair['arm_j']:<25} "
            f"{pair['b_i_only']:>4} {pair['c_j_only']:>4} "
            f"{pair['both_correct']:>8} {pair['both_wrong']:>8} "
            f"{pair['p_value']:>13.4f} {sig:>4}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="2026-05-14T00-53-19Z")
    args = parser.parse_args()

    run_dir = REPO / "data" / "multimodal_doc" / "runs" / args.run_id / "parser_compare"
    raw_path = run_dir / "raw.jsonl"
    post_path = run_dir / "raw_post_retry.jsonl"
    if not raw_path.exists() or not post_path.exists():
        raise SystemExit(
            "Missing raw.jsonl or raw_post_retry.jsonl. "
            "Run scripts/compute_post_retry_accuracy.py first."
        )

    raw_rows = _read_jsonl(raw_path)
    post_rows = _read_jsonl(post_path)

    print(f"Run: {args.run_id}")
    print(f"raw rows: {len(raw_rows)}, post-retry rows: {len(post_rows)}")

    # Latency uses post-retry rows (post-retry rows include the retry's own
    # latency for recovered rows). For raw, recovered rows have latency=0
    # because the harness recorded a failure.
    _print_latency("Per-arm latency (post-retry)", _per_arm_latency(post_rows))

    _print_tokens("Per-arm token distribution (post-retry)", _per_arm_tokens(post_rows))

    _print_pdf_var(
        "Per-PDF accuracy heterogeneity (post-retry)",
        _per_pdf_stats(post_rows),
    )

    _print_mcnemar(
        "McNemar pairwise (RAW, no retries)",
        _mcnemar_table(raw_rows),
    )
    _print_mcnemar(
        "McNemar pairwise (POST-RETRY)",
        _mcnemar_table(post_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
