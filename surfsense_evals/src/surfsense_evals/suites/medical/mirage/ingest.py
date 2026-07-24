"""MIRAGE ingestion.

Downloads:

* ``benchmark.json`` (≈ 4 MB; questions for the 5 sub-tasks).
* ``retrieved_snippets_10k.zip`` (the union of top-10k snippet ids
  retrieved by every retriever in the MedRAG paper, per task — a
  recall ceiling that avoids needing the full 23.9M-doc PubMed mirror).

Snippet *content* lives in the MedRAG HF mirrors
(``MedRAG/textbooks``, ``MedRAG/pubmed``, ``MedRAG/statpearls``,
``MedRAG/wikipedia``). We default to ``MedRAG/textbooks`` (212 MB,
125k snippets) which is the smallest and covers the majority of
``MedQA-US`` and the medical examination subsets. Operators can
opt into larger corpora with ``--corpus``.

Each snippet is written as one markdown file then batched into
``~5 MB`` markdown bundles for SurfSense's file upload (smaller
than backend default ``MAX_FILE_SIZE_BYTES`` and avoids the per-call
overhead of one HTTP request per snippet).

The ingestion produces two maps under ``data/medical/maps/``:

* ``mirage_snippet_map.jsonl`` — ``{snippet_id, document_id, batch_path}``
* ``mirage_chunk_map.jsonl`` — ``{chunk_id, document_id, snippet_id?}``
  (best-effort; chunk text is heuristically attributed to the
  snippet it overlaps when the SurfSense chunker splits a batched
  markdown).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx

from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.registry import RunContext

logger = logging.getLogger(__name__)


MIRAGE_BENCHMARK_URL = "https://raw.githubusercontent.com/Teddy-XiongGZ/MIRAGE/main/benchmark.json"
# Upstream only ships ONE zip — top-10k retrievals across 5 retrievers,
# ~16 GB. We default to skipping it (see `--skip-snippet-filter`) and
# ingesting the chosen corpus in full; this URL is only fetched when
# the operator explicitly opts in.
MIRAGE_SNIPPETS_ZIP_URL = (
    "https://virginia.box.com/shared/static/cxq17th6eisl2pn04vp0x723zczlvlzc.zip"
)


_DEFAULT_CORPUS = "MedRAG/textbooks"
_BATCH_SIZE_BYTES = 5 * 1024 * 1024
# 2 GB safety cap. Anything larger requires --allow-large-download.
# Set high enough that ``benchmark.json`` and small zips pass through
# untouched but the 16 GB MIRAGE retrievals zip trips the guard.
_LARGE_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024
_DOWNLOAD_RETRIES = 5
_RETRYABLE_NET_EXC: tuple[type[BaseException], ...] = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.ConnectTimeout,
)


@dataclass
class SnippetRow:
    snippet_id: str
    title: str
    content: str

    def to_markdown(self) -> str:
        title = (self.title or "").strip() or "Untitled"
        body = (self.content or "").strip()
        return f"# {title}\n\n_id: `{self.snippet_id}`_\n\n{body}\n"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def _reuse_cached_dest(dest: Path, *, expect_zip: bool, label: str) -> Path | None:
    """Return ``dest`` if a usable cache hit, else ``None`` (and delete corrupt zips)."""

    if not dest.exists():
        return None
    if expect_zip and not _is_valid_zip(dest):
        logger.warning(
            "Cached %s at %s failed ZIP validation (size=%d B); deleting and re-downloading.",
            label,
            dest,
            dest.stat().st_size,
        )
        dest.unlink(missing_ok=True)
        return None
    logger.info("Using cached %s at %s", label, dest)
    return dest


async def _fetch_to_path(
    url: str,
    *,
    dest: Path,
    label: str,
    timeout_s: float = 600.0,
    allow_large_download: bool = False,
    expect_zip: bool = False,
) -> Path:
    """Download ``url`` to ``dest`` with retry, atomic-rename, and
    HTTP ``Range`` resume.

    Operational properties:

    * If ``dest`` already exists *and* (when ``expect_zip`` is True) the
      cached file is a valid ZIP, returns it immediately. A corrupt ZIP
      is removed and re-downloaded — this is the safety net for the
      `box.com truncated 16 GB zip` failure mode where the previous
      run wrote a half-completed file then exited with an exception.
    * Bytes are written to ``<dest>.partial`` and renamed only after the
      stream completes cleanly (and, for zips, only after a quick
      central-directory check). A failure mid-download leaves the
      ``.partial`` file in place so the next attempt can resume from
      where it stopped via an HTTP ``Range`` header.
    * Retries on transient network errors (``RemoteProtocolError``,
      ``ReadError``, ``ReadTimeout``, ``ConnectError``,
      ``ConnectTimeout``) with exponential backoff, up to
      ``_DOWNLOAD_RETRIES``.
    * Aborts before downloading if the ``Content-Length`` (or already-
      downloaded ``.partial`` size) is over ``_LARGE_DOWNLOAD_BYTES``
      and ``allow_large_download`` is False, to keep an operator from
      surprise-grabbing 16 GB on a slow link.
    """

    cached = _reuse_cached_dest(dest, expect_zip=expect_zip, label=label)
    if cached is not None:
        return cached

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    last_exc: BaseException | None = None

    for attempt in range(1, _DOWNLOAD_RETRIES + 1):
        existing_bytes = partial.stat().st_size if partial.exists() else 0
        headers: dict[str, str] = {}
        if existing_bytes:
            headers["Range"] = f"bytes={existing_bytes}-"
            logger.info(
                "Resuming %s from byte %d (attempt %d/%d)",
                label,
                existing_bytes,
                attempt,
                _DOWNLOAD_RETRIES,
            )
        else:
            logger.info(
                "Downloading %s from %s (attempt %d/%d)",
                label,
                url,
                attempt,
                _DOWNLOAD_RETRIES,
            )

        try:
            async with (
                httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout_s, connect=20.0),
                    follow_redirects=True,
                ) as client,
                client.stream("GET", url, headers=headers) as response,
            ):
                if existing_bytes and response.status_code == 200:
                    logger.warning(
                        "Server ignored Range header for %s; restarting from 0.",
                        label,
                    )
                    partial.unlink(missing_ok=True)
                    existing_bytes = 0
                elif response.status_code == 416:
                    # Range not satisfiable — the .partial is at or
                    # past the end. Treat as "already downloaded";
                    # validate by closing and re-opening for atomic
                    # rename below.
                    logger.info(
                        "Server reports %s already complete (HTTP 416).",
                        label,
                    )
                elif response.status_code not in (200, 206):
                    response.raise_for_status()

                total_size = _planned_total_size(response, existing_bytes)
                if (
                    total_size is not None
                    and total_size > _LARGE_DOWNLOAD_BYTES
                    and not allow_large_download
                ):
                    raise _LargeDownloadAbort(label, total_size)

                mode = "ab" if existing_bytes else "wb"
                with partial.open(mode) as fh:
                    async for chunk in response.aiter_bytes(chunk_size=1 << 18):
                        fh.write(chunk)
            # Optional content sanity check before promoting to dest.
            if expect_zip and not _is_valid_zip(partial):
                raise zipfile.BadZipFile(
                    f"{label} downloaded to {partial} but failed central-"
                    "directory check; will retry."
                )
            partial.replace(dest)
            return dest
        except _LargeDownloadAbort:
            raise
        except _RETRYABLE_NET_EXC as exc:
            last_exc = exc
            wait = min(60.0, 2.0**attempt)
            logger.warning(
                "Network error fetching %s (%s: %s); retrying in %.0fs.",
                label,
                type(exc).__name__,
                exc,
                wait,
            )
            await asyncio.sleep(wait)
        except zipfile.BadZipFile as exc:
            last_exc = exc
            # Truncated body — drop the partial and retry from scratch.
            partial.unlink(missing_ok=True)
            wait = min(60.0, 2.0**attempt)
            logger.warning(
                "Truncated ZIP for %s; restarting from byte 0 in %.0fs.",
                label,
                wait,
            )
            await asyncio.sleep(wait)

    raise RuntimeError(
        f"Failed to download {label} after {_DOWNLOAD_RETRIES} attempts: {last_exc!s}"
    )


def _planned_total_size(response: httpx.Response, existing_bytes: int) -> int | None:
    """Best-effort total size including any already-buffered .partial bytes."""

    cl = response.headers.get("Content-Length")
    if not cl:
        return None
    try:
        remaining = int(cl)
    except ValueError:
        return None
    return existing_bytes + remaining


def _is_valid_zip(path: Path) -> bool:
    """Cheap ZIP validity check via central-directory parse."""

    try:
        with zipfile.ZipFile(path) as zf:
            # ``namelist`` forces the central directory to be parsed.
            zf.namelist()
        return True
    except (zipfile.BadZipFile, OSError):
        return False


class _LargeDownloadAbort(RuntimeError):
    """Raised when a download exceeds the safety threshold without opt-in."""

    def __init__(self, label: str, size_bytes: int) -> None:
        gb = size_bytes / (1024**3)
        super().__init__(
            f"{label} would download ~{gb:.1f} GB, above the {_LARGE_DOWNLOAD_BYTES / (1024**3):.0f} GB safety cap. "
            "Re-run with `--allow-large-download` to acknowledge, or use "
            "`--skip-snippet-filter` to bypass this download entirely and "
            "ingest the full corpus instead."
        )


def _read_snippet_ids(zip_path: Path, *, tasks: list[str]) -> dict[str, set[str]]:
    """Walk the ZIP for files whose path contains any task name.

    Each MedRAG retriever produces one JSON file per task in the zip;
    we union all retrievers' top-K ids. The exact directory layout has
    historically been ``<retriever>/<task>.json`` mapping
    ``question_id -> [snippet_id, ...]``.
    """

    out: dict[str, set[str]] = {t: set() for t in tasks}
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".json"):
                continue
            stem = Path(member).stem.lower()
            for task in tasks:
                if task.lower() in stem:
                    try:
                        with zf.open(member) as fh:
                            payload = json.loads(fh.read().decode("utf-8"))
                    except (json.JSONDecodeError, KeyError):
                        continue
                    for ids in payload.values():
                        if isinstance(ids, list):
                            for sid in ids:
                                if isinstance(sid, str):
                                    out[task].add(sid)
                                elif isinstance(sid, dict) and "id" in sid:
                                    out[task].add(str(sid["id"]))
                    break
    return out


def _load_corpus(corpus_name: str, snippet_ids: set[str] | None) -> Iterable[SnippetRow]:
    """Stream rows from a MedRAG HF corpus.

    * ``snippet_ids=None`` → yield every row (full-corpus ingestion path).
    * ``snippet_ids={...}`` → filter to the requested ids.

    Imported lazily — ``datasets`` is a heavyweight dep.
    """

    if snippet_ids is not None and not snippet_ids:
        return iter(())
    from datasets import load_dataset  # noqa: PLC0415

    logger.info("Loading corpus %s (this may take a while)", corpus_name)
    ds = load_dataset(corpus_name, split="train", streaming=True)
    for row in ds:
        sid = str(row.get("id") or "")
        if snippet_ids is not None and sid not in snippet_ids:
            continue
        yield SnippetRow(
            snippet_id=sid,
            title=str(row.get("title") or ""),
            content=str(row.get("content") or row.get("contents") or ""),
        )


# ---------------------------------------------------------------------------
# Batching + upload
# ---------------------------------------------------------------------------


@dataclass
class SnippetBatch:
    path: Path
    snippet_ids: list[str]


def _write_batches(
    snippets: Iterable[SnippetRow],
    *,
    out_dir: Path,
    batch_bytes: int = _BATCH_SIZE_BYTES,
    prefix: str = "mirage",
) -> list[SnippetBatch]:
    out_dir.mkdir(parents=True, exist_ok=True)
    batches: list[SnippetBatch] = []
    current_buffer = io.StringIO()
    current_ids: list[str] = []
    current_bytes = 0
    batch_idx = 0

    def _flush() -> None:
        nonlocal current_buffer, current_ids, current_bytes, batch_idx
        if not current_ids:
            return
        path = out_dir / f"{prefix}_{batch_idx:04d}.md"
        path.write_text(current_buffer.getvalue(), encoding="utf-8")
        batches.append(SnippetBatch(path=path, snippet_ids=current_ids))
        batch_idx += 1
        current_buffer = io.StringIO()
        current_ids = []
        current_bytes = 0

    for snippet in snippets:
        chunk = snippet.to_markdown() + "\n---\n\n"
        chunk_bytes = len(chunk.encode("utf-8"))
        if current_bytes + chunk_bytes > batch_bytes and current_ids:
            _flush()
        current_buffer.write(chunk)
        current_ids.append(snippet.snippet_id)
        current_bytes += chunk_bytes
    _flush()
    return batches


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_ingest(
    ctx: RunContext,
    *,
    tasks: list[str] | None = None,
    corpus: str = _DEFAULT_CORPUS,
    max_snippets_per_task: int | None = None,
    skip_snippet_filter: bool = True,
    allow_large_download: bool = False,
    settings: IngestSettings | None = None,
) -> None:
    """Ingest a MedRAG corpus into the suite SearchSpace.

    By default (``skip_snippet_filter=True``) we ingest the **entire**
    chosen corpus and let SurfSense's own retriever do the work. The
    upstream MIRAGE retrieval zip is ~16 GB and only useful when you
    want to pre-filter the corpus to the set of snippets some other
    retriever surfaced; for ``MedRAG/textbooks`` (212 MB / 125k snippets)
    that pre-filter is unnecessary overhead and routinely fails to
    download (box.com truncates the stream). Set
    ``skip_snippet_filter=False`` (CLI: ``--use-snippet-filter``) only
    if you specifically want the upstream filter — and budget the
    16 GB zip transfer.
    """

    tasks = tasks or ["mmlu", "medqa", "medmcqa", "pubmedqa", "bioasq"]
    settings = settings or IngestSettings(use_vision_llm=False, processing_mode="basic")

    bench_path = ctx.benchmark_data_dir() / "benchmark.json"
    await _fetch_to_path(MIRAGE_BENCHMARK_URL, dest=bench_path, label="MIRAGE benchmark.json")

    if skip_snippet_filter:
        logger.info(
            "Skipping retrieved_snippets_10k.zip (skip_snippet_filter=True); "
            "ingesting entire corpus %s.",
            corpus,
        )
        snippets = list(_load_corpus(corpus, snippet_ids=None))
    else:
        zip_path = ctx.benchmark_data_dir() / "retrieved_snippets_10k.zip"
        await _fetch_to_path(
            MIRAGE_SNIPPETS_ZIP_URL,
            dest=zip_path,
            label="MIRAGE retrieved_snippets_10k.zip",
            allow_large_download=allow_large_download,
            expect_zip=True,
        )

        by_task = _read_snippet_ids(zip_path, tasks=tasks)
        if max_snippets_per_task is not None:
            by_task = {k: set(list(v)[:max_snippets_per_task]) for k, v in by_task.items()}

        union_ids = set().union(*by_task.values())
        logger.info(
            "MIRAGE: tasks=%s, snippet ids per task: %s, union=%d",
            tasks,
            {k: len(v) for k, v in by_task.items()},
            len(union_ids),
        )
        if not union_ids:
            raise RuntimeError(
                f"No snippet ids parsed for tasks {tasks!r} from {zip_path}. "
                "Check the zip layout (the upstream archive may have changed)."
            )

        snippets = list(_load_corpus(corpus, snippet_ids=union_ids))
        logger.info(
            "Loaded %d / %d requested snippets from corpus %s",
            len(snippets),
            len(union_ids),
            corpus,
        )
    if not snippets:
        raise RuntimeError(
            f"Corpus {corpus} returned 0 matching rows. Either the snippet "
            "ids reference a different corpus (e.g. PubMed) or the HF mirror "
            "is unavailable. Pass --corpus to override."
        )

    batches_dir = ctx.benchmark_data_dir() / "batches"
    batches = _write_batches(snippets, out_dir=batches_dir)
    logger.info("Wrote %d snippet batches to %s", len(batches), batches_dir)

    docs_client = ctx.documents_client()
    upload_result = await docs_client.upload(
        files=[b.path for b in batches],
        search_space_id=ctx.search_space_id,
        use_vision_llm=settings.use_vision_llm,
        processing_mode=settings.processing_mode,
    )
    logger.info("MIRAGE upload settings: %s", settings.render_label())
    new_doc_ids = list(upload_result.document_ids)
    if new_doc_ids:
        await docs_client.wait_until_ready(
            search_space_id=ctx.search_space_id,
            document_ids=new_doc_ids,
            timeout_s=3600.0,
            max_poll_s=15.0,
        )

    statuses = await docs_client.get_status(
        search_space_id=ctx.search_space_id,
        document_ids=new_doc_ids + upload_result.duplicate_document_ids,
    )
    title_to_doc = {s.title: s.document_id for s in statuses}

    snippet_map_path = ctx.maps_dir() / "mirage_snippet_map.jsonl"
    chunk_map_path = ctx.maps_dir() / "mirage_chunk_map.jsonl"
    with snippet_map_path.open("w", encoding="utf-8") as fh:
        # Header line records the ingest-time settings (see
        # core/ingest_settings.py for the protocol).
        fh.write(settings_header_line(settings) + "\n")
        for batch in batches:
            doc_id = title_to_doc.get(batch.path.name)
            if doc_id is None:
                logger.warning("No document_id for batch %s", batch.path.name)
                continue
            for sid in batch.snippet_ids:
                fh.write(
                    json.dumps(
                        {
                            "snippet_id": sid,
                            "document_id": doc_id,
                            "batch_path": str(batch.path),
                        }
                    )
                    + "\n"
                )

    # Best-effort chunk map. SurfSense doesn't expose snippet attribution
    # per chunk, so we just record (chunk_id -> document_id) here; the
    # MIRAGE runner only needs document_id for accuracy scoring.
    with chunk_map_path.open("w", encoding="utf-8") as fh:
        for doc_id in {b.path.name and title_to_doc.get(b.path.name) for b in batches} - {None}:
            try:
                chunks = await docs_client.list_chunks(int(doc_id))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to list chunks for doc_id=%s: %s", doc_id, exc)
                continue
            for chunk in chunks:
                fh.write(json.dumps({"chunk_id": chunk.id, "document_id": doc_id}) + "\n")

    new_state = ctx.suite_state
    new_state.ingestion_maps["mirage"] = str(snippet_map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)
    logger.info("Wrote MIRAGE maps to %s and %s", snippet_map_path, chunk_map_path)


__all__ = ["run_ingest", "SnippetRow", "SnippetBatch"]
