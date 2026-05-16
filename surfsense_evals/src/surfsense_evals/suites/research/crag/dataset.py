"""CRAG dataset loader — download ``crag_task_1_and_2_dev_v4.jsonl.bz2`` and parse.

The CRAG repo (``facebookresearch/CRAG``) ships Tasks 1 & 2 as a
single bzip2-compressed JSONL on GitHub raw. Each row carries:

* ``interaction_id``    — opaque per-question id (we keep verbatim)
* ``query_time``        — wall clock of the original web search
* ``domain``            — finance | music | movie | sports | open
* ``question_type``     — simple | comparison | aggregation | set |
                          multi-hop | post-processing | false_premise |
                          simple_w_condition
* ``static_or_dynamic`` — static | slow-changing | fast-changing | real-time
* ``query``             — the question
* ``answer``            — gold short answer
* ``alt_ans``           — list[str] of alternative valid answers
                          (paraphrases / synonyms / unit variants)
* ``split``             — 0 = validation, 1 = public test
* ``popularity``        — head | torso | tail (KG questions); empty for web
* ``search_results``    — list of up to 5 ``{page_name, page_url,
                          page_snippet, page_result, page_last_modified}``;
                          ``page_result`` is full HTML.

We materialise this into ``CragQuestion`` objects keeping ``pages`` as
a list of ``CragPage`` so downstream ingest can save each as its own
file and SurfSense can dedupe on filename.
"""

from __future__ import annotations

import bz2
import hashlib
import io
import json
import logging
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Tasks 1 & 2 share the same JSONL on the public CRAG repo.
CRAG_TASK_1_2_URL = (
    "https://github.com/facebookresearch/CRAG/raw/refs/heads/main/data/"
    "crag_task_1_and_2_dev_v4.jsonl.bz2"
)
CRAG_TASK_1_2_FILENAME = "crag_task_1_and_2_dev_v4.jsonl.bz2"


# ---------------------------------------------------------------------------
# Question / page dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CragPage:
    """One of the up-to-5 pre-retrieved web pages for a CRAG question."""

    page_name: str
    page_url: str
    page_snippet: str
    page_html: str
    page_last_modified: str | None = None

    @property
    def url_hash(self) -> str:
        """Stable 12-hex digest of the page URL for filename keys.

        We can't use the raw URL as a filename (slashes, query strings,
        unicode), and we *do* want collision-safety across the whole
        ingest sample. ``sha1[:12]`` gives us 48 bits of namespace
        which is overkill for a corpus capped at a few thousand pages.
        """

        return hashlib.sha1(self.page_url.encode("utf-8")).hexdigest()[:12]


@dataclass
class CragQuestion:
    """One row of CRAG (Tasks 1 & 2)."""

    qid: str                          # synthesised "C00000".."C02705"
    interaction_id: str
    query_time: str
    query: str
    gold_answer: str
    alt_answers: list[str]
    domain: str
    question_type: str
    static_or_dynamic: str
    popularity: str                   # may be "" for web-sourced questions
    split: int                        # 0=validation, 1=public_test
    raw_index: int                    # row index in the source JSONL
    pages: list[CragPage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "qid": self.qid,
            "interaction_id": self.interaction_id,
            "query_time": self.query_time,
            "query": self.query,
            "gold_answer": self.gold_answer,
            "alt_answers": list(self.alt_answers),
            "domain": self.domain,
            "question_type": self.question_type,
            "static_or_dynamic": self.static_or_dynamic,
            "popularity": self.popularity,
            "split": self.split,
            "raw_index": self.raw_index,
            "n_pages": len(self.pages),
            "page_urls": [p.page_url for p in self.pages],
        }


# ---------------------------------------------------------------------------
# Download + decompress
# ---------------------------------------------------------------------------


def download_task_1_2(cache_dir: Path) -> Path:
    """Download the bz2 archive into ``cache_dir`` (skip if cached).

    Returns the path to the local ``.jsonl.bz2``. We use stdlib
    ``urllib`` rather than ``httpx`` to keep the download synchronous
    and trivially resumable (re-running the function is a no-op once
    the file is on disk and non-empty).
    """

    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / CRAG_TASK_1_2_FILENAME
    if dest.exists() and dest.stat().st_size > 0:
        logger.debug("CRAG bz2 already cached at %s", dest)
        return dest

    logger.info("Downloading CRAG (Tasks 1 & 2) from %s ...", CRAG_TASK_1_2_URL)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(
        CRAG_TASK_1_2_URL,
        headers={"User-Agent": "SurfSense-Evals/0.1 (CRAG dataset fetch)"},
    )
    with urllib.request.urlopen(req, timeout=600) as response, tmp.open("wb") as fh:
        chunk = response.read(1 << 20)
        while chunk:
            fh.write(chunk)
            chunk = response.read(1 << 20)
    tmp.replace(dest)
    logger.info("CRAG bz2 downloaded: %s (%.1f MiB)", dest, dest.stat().st_size / 1024 / 1024)
    return dest


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def _parse_pages(raw_search_results: Any) -> list[CragPage]:
    if not isinstance(raw_search_results, list):
        return []
    pages: list[CragPage] = []
    for entry in raw_search_results:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("page_url") or "").strip()
        html = str(entry.get("page_result") or "")
        if not url or not html.strip():
            # No URL or empty HTML => useless for retrieval.
            continue
        pages.append(CragPage(
            page_name=str(entry.get("page_name") or "").strip(),
            page_url=url,
            page_snippet=str(entry.get("page_snippet") or "").strip(),
            page_html=html,
            page_last_modified=(
                str(entry.get("page_last_modified")).strip()
                if entry.get("page_last_modified") else None
            ),
        ))
    return pages


def _parse_alt_answers(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def iter_questions(jsonl_bz2_path: Path) -> list[CragQuestion]:
    """Stream-decompress + parse the CRAG JSONL into ``CragQuestion`` objects.

    The bz2 expansion ratio is ~10x and the decompressed file is
    multi-GB; we therefore decompress *line by line* via
    ``bz2.open(..., "rt")``. Each row is a single (potentially very
    large, due to embedded HTML) JSON object. We keep the entire row
    in memory because we materialise the pages to disk immediately
    after parsing in the ingest pipeline — the runner never holds
    more than the current sample's worth of HTML.
    """

    out: list[CragQuestion] = []
    with bz2.open(jsonl_bz2_path, mode="rt", encoding="utf-8") as fh:
        for raw_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed CRAG row %d: %s", raw_idx, exc)
                continue
            query = str(row.get("query") or "").strip()
            answer = str(row.get("answer") or "").strip()
            if not query or not answer:
                logger.debug("Skipping CRAG row %d with missing query/answer", raw_idx)
                continue
            interaction_id = str(row.get("interaction_id") or "").strip()
            pages = _parse_pages(row.get("search_results"))
            out.append(CragQuestion(
                qid=f"C{raw_idx:05d}",
                interaction_id=interaction_id,
                query_time=str(row.get("query_time") or "").strip(),
                query=query,
                gold_answer=answer,
                alt_answers=_parse_alt_answers(row.get("alt_ans")),
                domain=str(row.get("domain") or "").strip().lower(),
                question_type=str(row.get("question_type") or "").strip().lower(),
                static_or_dynamic=str(row.get("static_or_dynamic") or "").strip().lower(),
                popularity=str(row.get("popularity") or "").strip().lower(),
                split=int(row.get("split") or 0),
                raw_index=raw_idx,
                pages=pages,
            ))
    return out


def stratified_sample(
    questions: list[CragQuestion],
    *,
    n: int,
    seed: int = 17,
) -> list[CragQuestion]:
    """Take ``n`` questions that roughly preserve the domain × question-type mix.

    CRAG is only ~2.7k rows so naive head-of-list sampling badly
    over-weights ``finance`` (because the dataset isn't shuffled by
    domain). We bucket on ``(domain, question_type)`` and round-robin
    pick from each bucket until we hit ``n`` — this gives every
    bucket a fair shot and keeps the sample composition stable across
    re-runs (deterministic via the seeded shuffle inside each bucket).
    """

    if n <= 0 or n >= len(questions):
        return list(questions)
    import random

    rng = random.Random(seed)
    buckets: dict[tuple[str, str], list[CragQuestion]] = {}
    for q in questions:
        buckets.setdefault((q.domain, q.question_type), []).append(q)
    for items in buckets.values():
        rng.shuffle(items)

    keys = sorted(buckets.keys())
    chosen: list[CragQuestion] = []
    cursor = 0
    while len(chosen) < n and any(buckets[k] for k in keys):
        key = keys[cursor % len(keys)]
        cursor += 1
        if buckets[key]:
            chosen.append(buckets[key].pop())
    chosen.sort(key=lambda q: q.raw_index)
    return chosen


def write_questions_jsonl(questions: list[CragQuestion], dest: Path) -> None:
    """Persist a parsed copy (without page HTML) under the benchmark data dir."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        for q in questions:
            fh.write(json.dumps(q.to_dict()) + "\n")


# ---------------------------------------------------------------------------
# Reading the lightweight questions.jsonl back
# ---------------------------------------------------------------------------


def load_questions_jsonl(path: Path) -> list[dict[str, Any]]:
    """Re-load the lightweight (no-HTML) questions JSONL from disk."""

    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# ---------------------------------------------------------------------------
# Convenience: decompress a snippet to memory for tests
# ---------------------------------------------------------------------------


def decompress_to_memory(jsonl_bz2_path: Path) -> io.StringIO:
    """For tests / one-off scripts: read the whole bz2 into a StringIO.

    Avoids leaking gigabytes; use ``iter_questions`` in production.
    """

    with bz2.open(jsonl_bz2_path, mode="rb") as fh:
        return io.StringIO(fh.read().decode("utf-8"))


__all__ = [
    "CRAG_TASK_1_2_FILENAME",
    "CRAG_TASK_1_2_URL",
    "CragPage",
    "CragQuestion",
    "decompress_to_memory",
    "download_task_1_2",
    "iter_questions",
    "load_questions_jsonl",
    "stratified_sample",
    "write_questions_jsonl",
]
