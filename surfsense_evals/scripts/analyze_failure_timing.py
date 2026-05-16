"""Were the SSL failures clustered in time (network blip) or evenly
distributed (sustained limit)? Group failures by 1-min buckets using
the run start time and the per-row latency_ms / answer order.

Also: for the one *real* intrinsic failure — the 30MB Anthropic limit
on 2405.09818v1.pdf::Q007 — print the full error message + raw payload
sizes so the blog has a clean root cause.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "data" / "multimodal_doc" / "runs" / "2026-05-14T00-53-19Z" / "parser_compare"
RAW = RUN / "raw.jsonl"
PDFS = REPO / "data" / "multimodal_doc" / "mmlongbench" / "pdfs"


def main() -> None:
    rows = [
        json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # 1) SSL clustering: failures by question index per arm
    by_arm_idx: dict[str, list[tuple[int, str]]] = defaultdict(list)
    qid_order: dict[str, int] = {}
    arm_seen_count: dict[str, int] = defaultdict(int)
    for row in rows:
        arm = row["arm"]
        idx = arm_seen_count[arm]
        arm_seen_count[arm] += 1
        qid_order[f"{arm}::{row['qid']}"] = idx
        err = row.get("error") or ""
        cluster = "ssl" if "SSLError" in err else (
            "empty" if not (row.get("raw_text") or "").strip() and not err else (
                "5xx" if "502" in err or "503" in err else (
                    "size_limit" if "exceeds" in err.lower() and "limit" in err.lower() else (
                        "other_err" if err else "ok"
                    )
                )
            )
        )
        if cluster != "ok":
            by_arm_idx[arm].append((idx, cluster))

    print("=" * 80)
    print("SSL/network-error indices per arm (each arm processes 171 questions in")
    print("order; index = sequential position within that arm). Tight clustering")
    print("in time = transient blip, even spread = sustained limit.")
    print("=" * 80)
    for arm in sorted(by_arm_idx):
        items = by_arm_idx[arm]
        if not items:
            continue
        idxs = sorted(set(i for i, _ in items))
        print(f"\n{arm}: {len(items)} failures at indices {idxs}")
        # show clusters
        cluster_runs = []
        cur = [idxs[0]]
        for i in idxs[1:]:
            if i - cur[-1] <= 5:  # within 5 questions = same time window
                cur.append(i)
            else:
                cluster_runs.append(cur)
                cur = [i]
        cluster_runs.append(cur)
        print(f"   clusters (gap<=5): {len(cluster_runs)}: {cluster_runs}")

    # 2) The 30MB intrinsic failure — full details
    print()
    print("=" * 80)
    print("Intrinsic failure: 30MB Anthropic input limit on 2405.09818v1.pdf::Q007")
    print("=" * 80)
    for row in rows:
        if row["qid"] == "2405.09818v1.pdf::Q007" and row["arm"] == "native_pdf":
            err = row.get("error") or ""
            print(f"  qid: {row['qid']}")
            print(f"  doc: {row['doc_id']}, pages: {row.get('pages')}")
            pdf_path = PDFS / row["doc_id"]
            if pdf_path.exists():
                size_mb = pdf_path.stat().st_size / (1024 * 1024)
                print(f"  PDF size on disk: {size_mb:.1f} MB")
                # base64 inflates ~33%
                est_b64 = size_mb * 1.33
                print(f"  estimated base64 wire size: {est_b64:.1f} MB")
            print(f"  full error: {err[:600]}")
            break

    # 3) Per-PDF: which PDFs are pathological?
    print()
    print("=" * 80)
    print("Per-PDF failure breakdown across all 6 arms (only PDFs with failures)")
    print("=" * 80)
    by_pdf: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        err = row.get("error") or ""
        empty = not (row.get("raw_text") or "").strip()
        if err or empty:
            by_pdf[row["doc_id"]].append({
                "arm": row["arm"],
                "qid": row["qid"],
                "err_kind": (
                    "ssl" if "SSLError" in err
                    else "size_limit" if "exceeds" in err.lower() and "limit" in err.lower()
                    else "5xx" if "502" in err or "503" in err
                    else "json_decode" if "JSONDecodeError" in err
                    else "empty" if empty and not err
                    else "other"
                ),
                "pages": row.get("pages"),
            })
    for doc, items in sorted(by_pdf.items(), key=lambda x: (-len(x[1]), x[0])):
        kinds = Counter(i["err_kind"] for i in items)
        arms = sorted({i["arm"] for i in items})
        pages = items[0]["pages"]
        print(f"  {doc}  pages={pages}  failures={len(items)}  arms={arms}")
        print(f"     kinds: {dict(kinds)}")


if __name__ == "__main__":
    main()
