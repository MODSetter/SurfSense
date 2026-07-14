"""CUREv1 ingestion.

For each (lang, discipline) requested, downloads the corpus split via
``datasets.load_dataset(path="clinia/CUREv1", name="corpus", split=<discipline>)``,
batches passages into ~5 MB markdown bundles, uploads them to
SurfSense, polls until ``ready``, and persists the
``corpus_id -> document_id`` map under
``data/medical/maps/cure_corpus_map_<discipline>.jsonl``. A union map
``cure_corpus_map.jsonl`` is also written so the runner can resolve
citations across disciplines without juggling per-file paths.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.registry import RunContext

logger = logging.getLogger(__name__)


_BATCH_SIZE_BYTES = 5 * 1024 * 1024

# 10 disciplines covered by the dataset card. We exhaustively list
# them so a smoke test can default to one.
DISCIPLINES = (
    "anesthesiology",
    "cardiology",
    "dermatology",
    "endocrinology",
    "gastroenterology",
    "hematology",
    "nephrology",
    "neurology",
    "obstetrics_gynecology",
    "psychiatry",
)


@dataclass
class CorpusPassage:
    corpus_id: str
    title: str
    text: str

    def to_markdown(self) -> str:
        title = (self.title or "").strip() or "Untitled"
        body = (self.text or "").strip()
        return f"# {title}\n\n_id: `{self.corpus_id}`_\n\n{body}\n"


@dataclass
class PassageBatch:
    path: Path
    corpus_ids: list[str]


def _stream_corpus(discipline: str) -> Iterable[CorpusPassage]:
    """Stream corpus rows for one discipline via the ``datasets`` library."""

    from datasets import load_dataset  # noqa: PLC0415

    logger.info("Loading CUREv1 corpus for discipline=%s", discipline)
    ds = load_dataset(path="clinia/CUREv1", name="corpus", split=discipline)
    for row in ds:
        cid = str(row.get("_id") or "")
        if not cid:
            continue
        yield CorpusPassage(
            corpus_id=cid,
            title=str(row.get("title") or ""),
            text=str(row.get("text") or ""),
        )


def _write_batches(
    passages: Iterable[CorpusPassage],
    *,
    out_dir: Path,
    discipline: str,
    batch_bytes: int = _BATCH_SIZE_BYTES,
) -> list[PassageBatch]:
    out_dir.mkdir(parents=True, exist_ok=True)
    batches: list[PassageBatch] = []
    current_buffer = io.StringIO()
    current_ids: list[str] = []
    current_bytes = 0
    batch_idx = 0

    def _flush() -> None:
        nonlocal current_buffer, current_ids, current_bytes, batch_idx
        if not current_ids:
            return
        path = out_dir / f"cure_{discipline}_{batch_idx:04d}.md"
        path.write_text(current_buffer.getvalue(), encoding="utf-8")
        batches.append(PassageBatch(path=path, corpus_ids=current_ids))
        batch_idx += 1
        current_buffer = io.StringIO()
        current_ids = []
        current_bytes = 0

    for passage in passages:
        chunk = passage.to_markdown() + "\n---\n\n"
        chunk_bytes = len(chunk.encode("utf-8"))
        if current_bytes + chunk_bytes > batch_bytes and current_ids:
            _flush()
        current_buffer.write(chunk)
        current_ids.append(passage.corpus_id)
        current_bytes += chunk_bytes
    _flush()
    return batches


async def run_ingest(
    ctx: RunContext,
    *,
    disciplines: list[str] | None = None,
    max_per_discipline: int | None = None,
    settings: IngestSettings | None = None,
) -> None:
    disciplines = disciplines or list(DISCIPLINES)
    settings = settings or IngestSettings(use_vision_llm=False, processing_mode="basic")
    bench_dir = ctx.benchmark_data_dir()
    batches_root = bench_dir / "batches"
    batches_root.mkdir(parents=True, exist_ok=True)

    docs_client = ctx.documents_client()
    union_map_path = ctx.maps_dir() / "cure_corpus_map.jsonl"
    union_map_fh = union_map_path.open("w", encoding="utf-8")
    # Header row records the ingest-time settings so the runner can
    # surface them in the report (see core/ingest_settings.py).
    union_map_fh.write(settings_header_line(settings) + "\n")
    try:
        for discipline in disciplines:
            try:
                passages_iter = _stream_corpus(discipline)
                if max_per_discipline is not None:
                    passages_iter = _take(passages_iter, max_per_discipline)
                batches = _write_batches(
                    passages_iter,
                    out_dir=batches_root / discipline,
                    discipline=discipline,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping discipline %s: %s", discipline, exc)
                continue
            if not batches:
                logger.warning("Discipline %s produced 0 batches; skipping upload", discipline)
                continue
            logger.info("Uploading %d batches for discipline %s", len(batches), discipline)
            upload_result = await docs_client.upload(
                files=[b.path for b in batches],
                search_space_id=ctx.search_space_id,
                use_vision_llm=settings.use_vision_llm,
                processing_mode=settings.processing_mode,
            )
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

            per_discipline_path = ctx.maps_dir() / f"cure_corpus_map_{discipline}.jsonl"
            with per_discipline_path.open("w", encoding="utf-8") as fh:
                fh.write(settings_header_line(settings) + "\n")
                for batch in batches:
                    doc_id = title_to_doc.get(batch.path.name)
                    if doc_id is None:
                        logger.warning("No document_id for batch %s", batch.path.name)
                        continue
                    for cid in batch.corpus_ids:
                        record = {
                            "corpus_id": cid,
                            "document_id": doc_id,
                            "discipline": discipline,
                        }
                        fh.write(json.dumps(record) + "\n")
                        union_map_fh.write(json.dumps(record) + "\n")

            chunks_map_path = ctx.maps_dir() / f"cure_chunk_map_{discipline}.jsonl"
            with chunks_map_path.open("w", encoding="utf-8") as fh:
                for doc_id in {title_to_doc.get(b.path.name) for b in batches} - {None}:
                    try:
                        chunks = await docs_client.list_chunks(int(doc_id))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to list chunks for doc_id=%s: %s", doc_id, exc)
                        continue
                    for chunk in chunks:
                        fh.write(
                            json.dumps(
                                {
                                    "chunk_id": chunk.id,
                                    "document_id": doc_id,
                                    "discipline": discipline,
                                }
                            )
                            + "\n"
                        )
    finally:
        union_map_fh.close()

    new_state = ctx.suite_state
    new_state.ingestion_maps["cure"] = str(union_map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)
    logger.info("CUREv1 ingestion complete; union map at %s", union_map_path)


def _take(it: Iterable, n: int) -> Iterable:
    for i, x in enumerate(it):
        if i >= n:
            return
        yield x


__all__ = ["DISCIPLINES", "CorpusPassage", "PassageBatch", "run_ingest"]
