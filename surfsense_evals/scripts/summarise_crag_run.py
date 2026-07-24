"""Render a quick textual summary of the latest CRAG run."""

from __future__ import annotations

import glob
import json


def main() -> None:
    runs = sorted(glob.glob("data/research/runs/*/crag/run_artifact.json"))
    if not runs:
        print("(no CRAG runs found)")
        return
    with open(runs[-1], encoding="utf-8") as fh:
        m = json.load(fh)
    metrics = m["metrics"]

    print(f"Reading: {runs[-1]}")
    print(f"n_questions: {m['extra']['n_questions']}")
    print()
    print("=== ARMS ===")
    for arm in ("bare_llm", "long_context", "surfsense"):
        d = metrics[arm]
        print(
            f"{arm:14s}: "
            f"acc={d['accuracy'] * 100:5.1f}% (Wilson 95% CI "
            f"{d['ci_low'] * 100:.1f}-{d['ci_high'] * 100:.1f}) | "
            f"correct={d['correct_rate'] * 100:5.1f}% "
            f"missing={d['missing_rate'] * 100:5.1f}% "
            f"incorrect={d['incorrect_rate'] * 100:5.1f}% | "
            f"truth={d['truthfulness_score'] * 100:+5.1f}%"
        )

    print()
    print("=== DELTAS ===")
    for key, d in metrics["deltas"].items():
        print(
            f"{key:30s}: acc={d['accuracy_pp']:+5.1f}pp "
            f"truth={d['truthfulness_score_pp']:+5.1f}pp "
            f"McNemar p={d['mcnemar_p_value']:.4f} ({d['mcnemar_method']}) "
            f"bootstrap CI [{d['bootstrap_ci_low']:+.1f}, {d['bootstrap_ci_high']:+.1f}]"
        )

    print()
    print("=== PER-QUESTION-TYPE TRUTHFULNESS ===")
    for qt, row in sorted(metrics["per_question_type"].items()):
        n = row["n"]
        pieces = [f"{qt:20s} (n={n:3d}):"]
        for arm in ("bare_llm", "long_context", "surfsense"):
            if arm in row:
                pieces.append(f"{arm}={row[arm]['truthfulness_score'] * 100:+7.1f}%")
        print(" ".join(pieces))

    print()
    print("=== PER-DOMAIN TRUTHFULNESS ===")
    for dom, row in sorted(metrics["per_domain"].items()):
        n = row["n"]
        pieces = [f"{dom:10s} (n={n:3d}):"]
        for arm in ("bare_llm", "long_context", "surfsense"):
            if arm in row:
                pieces.append(f"{arm}={row[arm]['truthfulness_score'] * 100:+7.1f}%")
        print(" ".join(pieces))


if __name__ == "__main__":
    main()
