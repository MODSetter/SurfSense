"""Stub the mmlongbench manifest so parser_compare can extract in parallel.

The mmlongbench Surfsense ingest writes its manifest only at the very
end of the upload pipeline (~hours of celery work). parser_compare's
ingest, on the other hand, just needs a list of (doc_id, pdf_path)
tuples to know which PDFs to extract — it doesn't care about the
SurfSense ``document_id`` (the runner does, later, after a refresh).

This script extends the existing manifest with the *additional* PDFs
that mmlongbench has already cached on disk (i.e. all 30 PDFs in
``data/multimodal_doc/mmlongbench/pdfs/`` even though only 5 have
SurfSense ``document_id``s yet) so parser_compare can run all four
extractions for them in parallel with the SurfSense ingest.

After mmlongbench finishes, re-run::

    python -m surfsense_evals ingest multimodal_doc parser_compare \
        --max-docs 30

…to refresh ``parser_compare_doc_map.jsonl`` with the now-populated
``document_id`` values for the 25 new PDFs. The extractions
themselves are cached on disk so the second pass is essentially free.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "data" / "multimodal_doc" / "maps" / "mmlongbench_doc_map.jsonl"
PDF_DIR = REPO / "data" / "multimodal_doc" / "mmlongbench" / "pdfs"
QUESTIONS = REPO / "data" / "multimodal_doc" / "mmlongbench" / "questions.jsonl"


def _question_count_per_doc() -> dict[str, int]:
    counts: dict[str, int] = {}
    with QUESTIONS.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            counts[row["doc_id"]] = counts.get(row["doc_id"], 0) + 1
    return counts


def main() -> None:
    if not MAP_PATH.exists():
        raise SystemExit(
            f"manifest not found at {MAP_PATH} — "
            "run `surfsense_evals ingest multimodal_doc mmlongbench` first."
        )

    existing_lines = MAP_PATH.read_text(encoding="utf-8").splitlines()
    existing_rows: list[dict] = []
    settings_line = None
    for line in existing_lines:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "__settings__" in row:
            settings_line = line
        else:
            existing_rows.append(row)

    by_doc_id = {r["doc_id"]: r for r in existing_rows}
    counts = _question_count_per_doc()

    cached_pdfs = sorted(p for p in PDF_DIR.glob("*.pdf"))
    print(f"existing manifest entries: {len(existing_rows)}")
    print(f"cached PDFs on disk:       {len(cached_pdfs)}")

    added = 0
    for pdf in cached_pdfs:
        if pdf.name in by_doc_id:
            continue
        by_doc_id[pdf.name] = {
            "doc_id": pdf.name,
            "document_id": None,
            "pdf_path": str(pdf),
            "n_questions": counts.get(pdf.name, 0),
        }
        added += 1

    out_lines: list[str] = []
    if settings_line:
        out_lines.append(settings_line)
    for doc_id in sorted(by_doc_id):
        out_lines.append(json.dumps(by_doc_id[doc_id]))
    MAP_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print(f"added {added} stub rows; manifest now has {len(by_doc_id)} PDFs")
    print(f"wrote: {MAP_PATH}")


if __name__ == "__main__":
    main()
