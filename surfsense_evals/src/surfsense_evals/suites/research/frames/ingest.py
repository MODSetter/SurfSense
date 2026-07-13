"""FRAMES ingestion: download → fetch Wikipedia → upload markdown.

Steps:

1. Download ``test.tsv`` from ``hf://datasets/google/frames-benchmark``.
2. Parse rows into ``FramesQuestion`` objects.
3. Optionally cap to the first ``--max-questions N`` so a smoke run
   doesn't trigger a 1k-article fetch.
4. Build the **deduplicated** set of Wikipedia URLs across the chosen
   sample (questions share many articles — Q1 and Q42 might both
   reference ``James_A._Garfield``).
5. Fetch each unique article via ``WikiFetcher`` (polite 2 RPS) into
   ``<bench_dir>/wiki/<title>.md``.
6. Upload the resulting markdown files to SurfSense in batches with
   ``use_vision_llm=False, processing_mode="basic"`` (text-only — no
   reason to pay vision LLM costs on Wikipedia plaintext).
7. Persist a doc map at
   ``<suite_data>/maps/frames_doc_map.jsonl`` with one row per question
   listing its ``document_ids`` (so the runner *could* scope retrieval
   if requested, though by default we don't — see ``runner.py``).

The doc map row shape:

    {"qid": "Q000",
     "wiki_titles": ["President of the United States", "James Buchanan", ...],
     "document_ids": [123, 124, ...],
     "missing_titles": []}

We resolve titles → SurfSense document_ids via the post-upload
``DocumentStatus.title`` field. SurfSense's title is the uploaded
filename (without extension), so we round-trip via
``cache_filename_for_title`` to match.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.clients.documents import (
    DocumentProcessingFailed,
    DocumentProcessingTimeout,
)
from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.registry import RunContext
from .dataset import (
    download_test_tsv,
    load_questions,
    write_questions_jsonl,
)
from .wiki_fetch import (
    WikiArticle,
    WikiFetcher,
    cache_filename_for_title,
    title_from_url,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _IngestStats:
    n_questions: int
    n_unique_urls: int
    n_fetched: int
    n_cached_hits: int
    n_missing: int
    n_uploaded: int
    n_existing: int
    bench_dir: Path
    map_path: Path


async def _fetch_articles(
    fetcher: WikiFetcher,
    urls: list[str],
) -> tuple[dict[str, WikiArticle], list[str]]:
    """Fetch each URL serially (the WikiFetcher's rate-limiter serialises anyway).

    Returns ``(url -> WikiArticle, missing_urls)``. Missing means
    Wikipedia reported the title doesn't exist, the URL was non-wiki,
    or the API returned an empty extract.
    """

    fetched: dict[str, WikiArticle] = {}
    missing: list[str] = []
    n_total = len(urls)
    for i, url in enumerate(urls, start=1):
        try:
            article = await fetcher.fetch(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("FRAMES wiki fetch %s failed: %s", url, exc)
            missing.append(url)
            continue
        if article is None:
            missing.append(url)
            continue
        fetched[url] = article
        if i % 25 == 0 or i == n_total:
            logger.info("  ... fetched %d / %d Wikipedia articles", i, n_total)
    return fetched, missing


async def _upload_markdowns(
    ctx: RunContext,
    articles: list[WikiArticle],
    *,
    batch_size: int,
    settings: IngestSettings,
) -> dict[str, int]:
    """Upload deduplicated markdown files. Returns ``filename -> document_id``.

    SurfSense dedupes uploads on ``(filename, search_space_id)``, so
    re-running ingest after a crash is idempotent — duplicates land in
    ``duplicate_document_ids`` and we still recover their ids via the
    status endpoint.
    """

    if not articles:
        return {}
    docs_client = ctx.documents_client()
    name_to_id: dict[str, int] = {}
    paths = [a.markdown_path for a in articles]
    for batch_start in range(0, len(paths), batch_size):
        batch = paths[batch_start : batch_start + batch_size]
        result = await docs_client.upload(
            files=batch,
            search_space_id=ctx.search_space_id,
            use_vision_llm=settings.use_vision_llm,
            processing_mode=settings.processing_mode,
        )
        all_ids = list(result.document_ids) + list(result.duplicate_document_ids)
        if result.document_ids:
            try:
                await docs_client.wait_until_ready(
                    search_space_id=ctx.search_space_id,
                    document_ids=result.document_ids,
                    timeout_s=900.0,
                )
            except (DocumentProcessingFailed, DocumentProcessingTimeout) as exc:
                logger.warning("FRAMES batch processing issue: %s", exc)
        if all_ids:
            statuses = await docs_client.get_status(
                search_space_id=ctx.search_space_id,
                document_ids=all_ids,
            )
            for s in statuses:
                # SurfSense stores the uploaded filename as ``title`` (no extension).
                stem = Path(s.title).stem if s.title.endswith(".md") else s.title
                name_to_id[stem] = s.document_id
                name_to_id[s.title] = s.document_id
        logger.info(
            "FRAMES upload batch %d-%d: %d new, %d duplicate",
            batch_start, batch_start + len(batch),
            len(result.document_ids), len(result.duplicate_document_ids),
        )
    return name_to_id


def _resolve_question_doc_ids(
    questions: list[Any],
    fetched: dict[str, WikiArticle],
    name_to_id: dict[str, int],
) -> list[dict[str, Any]]:
    """For each question, list the document_ids of its (fetched) wiki articles."""

    rows: list[dict[str, Any]] = []
    for q in questions:
        doc_ids: list[int] = []
        titles: list[str] = []
        missing: list[str] = []
        for url in q.wiki_urls:
            article = fetched.get(url)
            if article is None:
                missing.append(url)
                continue
            titles.append(article.title)
            stem = Path(cache_filename_for_title(article.title)).stem
            doc_id = name_to_id.get(stem) or name_to_id.get(article.markdown_path.name)
            if doc_id is not None and doc_id not in doc_ids:
                doc_ids.append(doc_id)
        rows.append({
            "qid": q.qid,
            "raw_index": q.raw_index,
            "n_wiki_urls": len(q.wiki_urls),
            "wiki_titles": titles,
            "document_ids": doc_ids,
            "missing_urls": missing,
        })
    return rows


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_ingest(
    ctx: RunContext,
    *,
    max_questions: int | None = None,
    upload_batch_size: int = 16,
    skip_upload: bool = False,
    fetch_rate_limit_rps: float = 2.0,
    settings: IngestSettings | None = None,
) -> None:
    """Ingest the FRAMES benchmark into the research suite.

    Parameters
    ----------
    max_questions : int | None
        Cap on the number of FRAMES questions to materialise. ``None`` =
        all 824 (≈300+ unique articles). Smoke runs should pass 5-10.
    upload_batch_size : int
        Markdown files per ``/documents/fileupload`` call. Larger
        batches reduce round-trip overhead; smaller batches recover
        faster from individual processing failures.
    skip_upload : bool
        Fetch + cache Wikipedia articles locally but don't push to
        SurfSense. Useful for debugging the fetcher in isolation.
    fetch_rate_limit_rps : float
        Maximum requests-per-second to the Wikipedia API. Default 2.0
        is a polite ceiling; raise cautiously.
    settings : IngestSettings | None
        Override per-upload knobs. FRAMES defaults to text-only
        (no vision LLM, basic mode) — the corpus is plain wikitext.
    """

    settings = settings or IngestSettings(
        use_vision_llm=False,
        processing_mode="basic",
        )
    bench_dir = ctx.benchmark_data_dir()
    wiki_cache = bench_dir / "wiki"
    wiki_cache.mkdir(parents=True, exist_ok=True)
    hf_cache = bench_dir / ".hf_cache"
    hf_cache.mkdir(parents=True, exist_ok=True)

    # 1. Download + parse questions.
    tsv_path = download_test_tsv(hf_cache)
    questions = load_questions(tsv_path)
    if not questions:
        raise RuntimeError(
            "FRAMES test.tsv contained no parseable rows; upstream may "
            "have changed schema."
        )
    logger.info("FRAMES: parsed %d questions from %s", len(questions), tsv_path.name)
    if max_questions is not None and max_questions > 0:
        questions = questions[:max_questions]
        logger.info("FRAMES: capped to first %d questions", len(questions))

    questions_jsonl = bench_dir / "questions.jsonl"
    write_questions_jsonl(questions, questions_jsonl)

    # 2. Build deduplicated URL set (preserving first-seen order).
    seen_urls: dict[str, None] = {}
    for q in questions:
        for url in q.wiki_urls:
            seen_urls.setdefault(url, None)
    unique_urls = list(seen_urls.keys())
    logger.info(
        "FRAMES: %d unique Wikipedia URLs across %d questions",
        len(unique_urls), len(questions),
    )

    # 3. Fetch (with cache).
    fetcher = WikiFetcher(cache_dir=wiki_cache, rate_limit_rps=fetch_rate_limit_rps)
    n_cached = sum(
        1 for url in unique_urls
        if (wiki_cache / cache_filename_for_title(_safe_title(url))).exists()
    )
    fetched, missing_urls = await _fetch_articles(fetcher, unique_urls)
    logger.info(
        "FRAMES: fetched=%d, cache_hits=%d, missing=%d",
        len(fetched), n_cached, len(missing_urls),
    )

    # 4. Upload to SurfSense (deduped by filename).
    name_to_id: dict[str, int] = {}
    if skip_upload:
        logger.info("FRAMES: --skip-upload; skipping SurfSense ingestion")
    else:
        unique_articles = list({a.markdown_path: a for a in fetched.values()}.values())
        name_to_id = await _upload_markdowns(
            ctx,
            unique_articles,
            batch_size=upload_batch_size,
            settings=settings,
        )

    # 5. Persist per-question doc map.
    doc_rows = _resolve_question_doc_ids(questions, fetched, name_to_id)

    map_path = ctx.maps_dir() / "frames_doc_map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        fh.write(settings_header_line(settings) + "\n")
        for row in doc_rows:
            fh.write(json.dumps(row) + "\n")
    logger.info("Wrote FRAMES doc map to %s (%d rows)", map_path, len(doc_rows))

    # 6. Update suite state.
    new_state = ctx.suite_state
    new_state.ingestion_maps["frames"] = str(map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)

    stats = _IngestStats(
        n_questions=len(questions),
        n_unique_urls=len(unique_urls),
        n_fetched=len(fetched),
        n_cached_hits=n_cached,
        n_missing=len(missing_urls),
        n_uploaded=len(name_to_id),
        n_existing=0,
        bench_dir=bench_dir,
        map_path=map_path,
    )
    logger.info("FRAMES ingest done: %s", stats)


def _safe_title(url: str) -> str:
    """Pre-cache title resolution; returns ``""`` on bad URL."""

    try:
        return title_from_url(url)
    except ValueError:
        return ""


__all__ = ["run_ingest"]
