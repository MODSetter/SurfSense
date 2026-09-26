"""Fetch LIMIT-small into the retrieval eval, for the lexical-match case.

LIMIT (arXiv 2508.21038, ICLR 2026) shows what a single-vector embedding model
cannot represent: BM25 is near perfect on it while dense models score under 20%
recall@100. That is this app's ranking in miniature, since the final order is
cosine alone and BM25 gets no vote, so it measures what discarding that vote
costs on data nobody here wrote.

    uv run scripts/fetch_limit_small.py

Writes `retrieval_eval/local/`, which is gitignored: the data is CC-BY-4.0 and
stays out of the tree. Without it the eval runs on the authored corpus alone.
"""

import json
import sys

import httpx
from retrieval_eval.cases import LOCAL_DIR

ROWS = "https://datasets-server.huggingface.co/rows"
DATASET = "orionweller/LIMIT-small"
SOURCE = f"https://huggingface.co/datasets/{DATASET}"
# 1,000 queries is more than a per-run slice needs, and every one costs an
# embed. Every fifth keeps the mix and the run short.
EVERY = 5
PAGE = 100


def page(config: str, split: str, offset: int, length: int) -> dict:
    reply = httpx.get(
        ROWS,
        params={
            "dataset": DATASET,
            "config": config,
            "split": split,
            "offset": offset,
            "length": length,
        },
        timeout=60.0,
    )
    reply.raise_for_status()
    return reply.json()


def every_row(config: str, split: str) -> list[dict]:
    first = page(config, split, 0, PAGE)
    rows = [item["row"] for item in first["rows"]]
    total = first["num_rows_total"]
    while len(rows) < total:
        rows += [item["row"] for item in page(config, split, len(rows), PAGE)["rows"]]
    return rows


def main() -> int:
    corpus_dir = LOCAL_DIR / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    documents = every_row("corpus", "corpus")
    for document in documents:
        # The id is the subject of its own sentence ("Ada Lovelace likes …"),
        # which is what a query has to find, so it is also the expected text.
        name = str(document["_id"])
        body = str(document.get("text") or "").strip()
        (corpus_dir / f"limit-{_slug(name)}.md").write_text(
            f"# {name}\n\n{body}\n", encoding="utf-8"
        )

    queries = {
        str(row["_id"]): str(row["text"]) for row in every_row("queries", "queries")
    }
    relevant: dict[str, list[str]] = {}
    for row in every_row("default", "test"):
        if int(row.get("score", 0)) > 0:
            relevant.setdefault(str(row["query-id"]), []).append(str(row["corpus-id"]))

    kept = sorted(relevant)[::EVERY]
    (LOCAL_DIR / "queries.json").write_text(
        json.dumps(
            [
                {
                    "id": f"limit-{query_id}",
                    "slice": "limit",
                    "text": queries[query_id],
                    "expect": relevant[query_id],
                }
                for query_id in kept
                if query_id in queries
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (LOCAL_DIR / "SOURCE.md").write_text(
        f"# LIMIT-small\n\nFetched from {SOURCE} by `scripts/fetch_limit_small.py`.\n"
        "CC-BY-4.0. Not committed; re-fetch rather than copy it into the repo.\n",
        encoding="utf-8",
    )
    print(f"{len(documents)} documents and {len(kept)} queries in {LOCAL_DIR}")
    return 0


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-")


if __name__ == "__main__":
    sys.exit(main())
