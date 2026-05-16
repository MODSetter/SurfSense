"""FRAMES dataset loader — download ``test.tsv`` from HF and parse rows.

The HF repo (``google/frames-benchmark``) ships a single tab-separated
file at ``test.tsv`` (824 rows). Columns of interest for us:

* unnamed first column → row index (``id`` we synthesise as ``Q000``..)
* ``Prompt``  → the question (free-text, often multi-clause)
* ``Answer``  → gold answer (short string: name, number, year, ...)
* ``wikipedia_link_1`` ... ``wikipedia_link_11+`` → sparse per-question
  link cells (we ignore in favour of the consolidated column below).
* ``reasoning_types`` → pipe-separated tags (``"Numerical reasoning |
  Tabular reasoning | Multiple constraints"``)
* ``wiki_links`` → Python-list literal of every URL the question relies
  on, e.g. ``"['https://en.wikipedia.org/wiki/...', '...']"``

We use ``wiki_links`` (already deduplicated per row) and
``ast.literal_eval`` to materialise it. The legacy
``wikipedia_link_*`` columns are kept around only so a curious
operator can compare cell-vs-list if upstream ever drift apart.
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


HF_REPO_ID = "google/frames-benchmark"
HF_REPO_TYPE = "dataset"
HF_TEST_FILE = "test.tsv"


def _hf_hub_download(*args: Any, **kwargs: Any) -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(*args, **kwargs)


# ---------------------------------------------------------------------------
# Question dataclass
# ---------------------------------------------------------------------------


@dataclass
class FramesQuestion:
    """One row of FRAMES (post-parse)."""

    qid: str                   # synthesised "Q000" .. "Q823"
    question: str
    gold_answer: str
    wiki_urls: list[str]       # deduped, in original order
    reasoning_types: list[str] # split on "|"
    raw_index: int             # row index from the TSV (for debugging)

    def to_dict(self) -> dict[str, Any]:
        return {
            "qid": self.qid,
            "question": self.question,
            "gold_answer": self.gold_answer,
            "wiki_urls": list(self.wiki_urls),
            "reasoning_types": list(self.reasoning_types),
            "raw_index": self.raw_index,
        }


# ---------------------------------------------------------------------------
# Download + parse
# ---------------------------------------------------------------------------


def download_test_tsv(cache_dir: Path) -> Path:
    """Resumable download of ``test.tsv`` via ``huggingface_hub``."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    local = _hf_hub_download(
        repo_id=HF_REPO_ID,
        filename=HF_TEST_FILE,
        repo_type=HF_REPO_TYPE,
        cache_dir=str(cache_dir),
    )
    return Path(local)


def _parse_wiki_links(raw: Any) -> list[str]:
    """Convert the ``wiki_links`` cell (Python list literal) to ``list[str]``."""

    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        # Fall back: maybe it's a comma-separated string with no quotes.
        return [tok.strip() for tok in text.strip("[]").split(",") if tok.strip()]
    if isinstance(parsed, (list, tuple)):
        return [str(x).strip() for x in parsed if str(x).strip()]
    return [str(parsed).strip()]


def _parse_reasoning_types(raw: Any) -> list[str]:
    if not raw:
        return []
    text = str(raw).strip()
    if not text:
        return []
    return [tok.strip() for tok in text.split("|") if tok.strip()]


def load_questions(tsv_path: Path) -> list[FramesQuestion]:
    """Read FRAMES rows from disk into ``FramesQuestion`` objects.

    Uses pandas for robust TSV parsing (tabs inside quoted strings are
    rare in this dataset but pandas handles them; the stdlib ``csv``
    module is fine too if pandas ever becomes a problem). We pin
    ``index_col=0`` because the upstream TSV uses the first unnamed
    column as the row index.
    """

    import pandas as pd

    df = pd.read_csv(tsv_path, sep="\t", index_col=0, keep_default_na=False)
    out: list[FramesQuestion] = []
    for raw_idx, row in df.iterrows():
        prompt = str(row.get("Prompt") or "").strip()
        answer = str(row.get("Answer") or "").strip()
        if not prompt or not answer:
            logger.debug("Skipping FRAMES row %s with missing Prompt/Answer", raw_idx)
            continue
        urls = _parse_wiki_links(row.get("wiki_links"))
        if not urls:
            # Fall back to the per-cell ``wikipedia_link_*`` columns.
            urls = []
            for col in row.index:
                if col.startswith("wikipedia_link"):
                    val = str(row.get(col) or "").strip()
                    if val and val not in urls:
                        urls.append(val)
        reasoning = _parse_reasoning_types(row.get("reasoning_types"))
        out.append(FramesQuestion(
            qid=f"Q{int(raw_idx):03d}",
            question=prompt,
            gold_answer=answer,
            wiki_urls=urls,
            reasoning_types=reasoning,
            raw_index=int(raw_idx),
        ))
    return out


def write_questions_jsonl(questions: list[FramesQuestion], dest: Path) -> None:
    """Persist a parsed copy under the benchmark data dir."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        for q in questions:
            fh.write(json.dumps(q.to_dict()) + "\n")


__all__ = [
    "FramesQuestion",
    "download_test_tsv",
    "load_questions",
    "write_questions_jsonl",
]
