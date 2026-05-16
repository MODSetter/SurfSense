"""Query SurfSense for the status of every MMLongBench PDF in scope.

Uses the existing SurfSense documents client to query
``/documents/status?document_ids=...`` for both the known-existing 5
PDFs (doc ids 5219-5223) and the recently-uploaded mmlongbench batch
(7577-7600 range).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


REPO = Path(__file__).resolve().parents[1]
PDF_DIR = REPO / "data" / "multimodal_doc" / "mmlongbench" / "pdfs"


async def main() -> None:
    load_dotenv(REPO / ".env")
    base = os.environ.get("SURFSENSE_API_BASE", "http://localhost:8000").rstrip("/")
    token = os.environ.get("SURFSENSE_JWT")
    if not token:
        raise SystemExit("SURFSENSE_JWT missing from .env")

    pdf_names = sorted(p.name for p in PDF_DIR.glob("*.pdf"))
    print(f"local cached PDFs: {len(pdf_names)}")

    candidate_ids = list(range(5219, 5224)) + list(range(7577, 7625))

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as http:
        r = await http.get(
            f"{base}/api/v1/documents/status",
            params={
                "search_space_id": 55,
                "document_ids": ",".join(str(d) for d in candidate_ids),
            },
            headers=headers,
        )
        r.raise_for_status()
        items = r.json().get("items", [])

    by_title: dict[str, dict] = {}
    for it in items:
        by_title[it.get("title", "")] = {
            "id": it.get("id"),
            "state": (it.get("status") or {}).get("state"),
            "reason": (it.get("status") or {}).get("reason"),
        }

    by_state: dict[str, int] = {}
    print()
    for name in pdf_names:
        info = by_title.get(name)
        if info is None:
            print(f"  [missing      ]              {name}")
            by_state["missing"] = by_state.get("missing", 0) + 1
        else:
            tag = info["state"] or "?"
            print(f"  [{tag:13s}] doc_id={info['id']:>5}  {name}")
            by_state[tag] = by_state.get(tag, 0) + 1
    print()
    print("summary:")
    for k, v in sorted(by_state.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
