"""CUREv1 runner — single-arm SurfSense retrieval scoring.

For each query we ask SurfSense via ``/api/v1/new_chat`` (no
``mentioned_document_ids``) and parse chunk citations from the
streamed answer. Cited ``chunk_id`` → ``document_id`` (chunk map) →
``corpus_id`` (corpus map). The resulting ranked list is scored
against the dataset's qrels.

The prompt nudges the model to surface its supporting passages via
SurfSense's standard ``[citation:CHUNK_ID]`` format (already required
by the agent system prompt), so we recover retrieval ordering from
the answer text without needing a separate retrieval API.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.arms import ArmRequest, ArmResult, SurfSenseArm
from ....core.config import utc_iso_timestamp
from ....core.ingest_settings import (
    IngestSettings,
    add_ingest_settings_args,
    format_ingest_settings_md,
    is_settings_header,
    read_settings_header,
)
from ....core.metrics.retrieval import score_run
from ....core.registry import (
    Benchmark,
    ReportSection,
    RunArtifact,
    RunContext,
)

logger = logging.getLogger(__name__)


_PROMPT = """\
You are a medical literature retrieval assistant for the question
below. Identify the top passages from the knowledge base that best
answer it and cite each one in the standard format
[citation:CHUNK_ID]. List as many citations as are useful, ordered
from most to least relevant. Provide a one-sentence justification
for each citation.

Query: {query}
"""


_DESCRIPTION = "CUREv1 retrieval (single-arm SurfSense): Recall@k / MRR / nDCG@10."

# CUREv1 corpus is text-only markdown bundles; vision LLM at ingest
# is wasted by default but the operator can flip it via CLI for an
# A/B comparison.
_DEFAULT_INGEST_SETTINGS = IngestSettings(
    use_vision_llm=False,
    processing_mode="basic",
)


@dataclass
class CureQuery:
    qid: str
    text: str
    discipline: str


def _load_chunk_map(maps_dir: Path) -> dict[int, int]:
    """Union all ``cure_chunk_map_<discipline>.jsonl`` into one dict."""

    out: dict[int, int] = {}
    for path in sorted(maps_dir.glob("cure_chunk_map_*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                if is_settings_header(row):
                    continue
                try:
                    out[int(row["chunk_id"])] = int(row["document_id"])
                except (KeyError, TypeError, ValueError):
                    continue
    return out


def _load_doc_to_corpus(maps_dir: Path) -> dict[int, list[str]]:
    """Map ``document_id -> [corpus_id, ...]`` from the union map.

    Multiple corpus passages may live in one batched markdown
    document, so each doc_id maps to a list. Citation ordering of the
    first occurrence is preserved.
    """

    out: dict[int, list[str]] = defaultdict(list)
    union_path = maps_dir / "cure_corpus_map.jsonl"
    if not union_path.exists():
        return out
    with union_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if is_settings_header(row):
                continue
            try:
                out[int(row["document_id"])].append(str(row["corpus_id"]))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def _load_queries(*, lang: str, disciplines: list[str], sample_n: int | None) -> list[CureQuery]:
    from datasets import load_dataset  # noqa: PLC0415

    out: list[CureQuery] = []
    for discipline in disciplines:
        try:
            ds = load_dataset(path="clinia/CUREv1", name=f"queries-{lang}", split=discipline)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping queries for %s/%s: %s", lang, discipline, exc)
            continue
        for row in ds:
            qid = str(row.get("_id") or "")
            text = str(row.get("text") or "")
            if not qid or not text:
                continue
            out.append(CureQuery(qid=qid, text=text, discipline=discipline))
    out.sort(key=lambda q: (q.discipline, q.qid))
    if sample_n is not None and sample_n > 0:
        # Stratified-by-discipline slice.
        per_d = max(1, sample_n // max(1, len(disciplines)))
        sliced: list[CureQuery] = []
        counter: dict[str, int] = defaultdict(int)
        for q in out:
            if counter[q.discipline] >= per_d:
                continue
            sliced.append(q)
            counter[q.discipline] += 1
            if len(sliced) >= sample_n:
                break
        out = sliced
    return out


def _load_qrels(*, disciplines: list[str]) -> dict[str, dict[str, float]]:
    from datasets import load_dataset  # noqa: PLC0415

    out: dict[str, dict[str, float]] = defaultdict(dict)
    for discipline in disciplines:
        try:
            ds = load_dataset(path="clinia/CUREv1", name="qrels", split=discipline)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping qrels for %s: %s", discipline, exc)
            continue
        for row in ds:
            qid = str(row.get("query-id") or row.get("query_id") or "")
            cid = str(row.get("corpus-id") or row.get("corpus_id") or "")
            score = row.get("score")
            if not qid or not cid or score is None:
                continue
            try:
                out[qid][cid] = float(score)
            except (TypeError, ValueError):
                continue
    return out


async def _gather_with_limit(coros, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(c):
        async with sem:
            return await c

    return await asyncio.gather(*(_wrap(c) for c in coros))


class CureBenchmark:
    suite: str = "medical"
    name: str = "cure"
    headline: bool = False
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--lang", default="en", choices=("en", "es", "fr"))
        parser.add_argument("--discipline", default=None,
                            help="Restrict to one discipline (default: all ingested).")
        parser.add_argument("--n", dest="sample_n", type=int, default=None)
        parser.add_argument("--concurrency", type=int, default=4)
        parser.add_argument(
            "--max-passages-per-discipline", type=int, default=None,
            help="(ingest only) cap corpus rows per discipline for smoke testing.",
        )
        # Per-upload knobs forwarded to /documents/fileupload at ingest;
        # ignored at run-time (runner reads resolved settings from the
        # union-map header).
        add_ingest_settings_args(parser, defaults=_DEFAULT_INGEST_SETTINGS)

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import DISCIPLINES, run_ingest

        settings = IngestSettings.merge(_DEFAULT_INGEST_SETTINGS, opts)
        await run_ingest(
            ctx,
            disciplines=list(DISCIPLINES),
            max_per_discipline=opts.get("max_passages_per_discipline"),
            settings=settings,
        )

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        lang = opts.get("lang") or "en"
        discipline_filter = opts.get("discipline")
        sample_n = opts.get("sample_n")
        concurrency = int(opts.get("concurrency") or 4)

        maps_dir = ctx.maps_dir()
        chunk_to_doc = _load_chunk_map(maps_dir)
        doc_to_corpus = _load_doc_to_corpus(maps_dir)
        ingest_settings = read_settings_header(maps_dir / "cure_corpus_map.jsonl")
        if not chunk_to_doc or not doc_to_corpus:
            raise RuntimeError(
                "CUREv1 not ingested for this suite. Run "
                "`python -m surfsense_evals ingest medical cure` first."
            )

        # Disciplines to query are determined by the per-discipline maps
        # actually present (either user-filtered or whatever was ingested).
        ingested_disciplines = sorted({
            row_disc
            for path in maps_dir.glob("cure_corpus_map_*.jsonl")
            for row_disc in [path.stem[len("cure_corpus_map_"):]]
        })
        if discipline_filter:
            disciplines = [discipline_filter]
        else:
            disciplines = ingested_disciplines or ["dermatology"]

        queries = _load_queries(lang=lang, disciplines=disciplines, sample_n=sample_n)
        if not queries:
            raise RuntimeError(
                f"No CUREv1 queries matched lang={lang!r} disciplines={disciplines!r}."
            )
        qrels = _load_qrels(disciplines=disciplines)
        logger.info(
            "CUREv1: %d queries / %d qrels across disciplines %s",
            len(queries),
            len(qrels),
            disciplines,
        )

        arm = SurfSenseArm(
            client=ctx.new_chat_client(),
            search_space_id=ctx.search_space_id,
            ephemeral_threads=True,
        )

        async def _ask(q: CureQuery) -> ArmResult:
            return await arm.answer(
                ArmRequest(
                    question_id=f"{q.discipline}::{q.qid}",
                    prompt=_PROMPT.format(query=q.text.strip()),
                )
            )

        results: list[ArmResult] = await _gather_with_limit(
            (_ask(q) for q in queries), concurrency=concurrency
        )

        per_query_retrieved: dict[str, list[str]] = {}
        for q, res in zip(queries, results):
            chunk_ids: list[int] = []
            seen: set[int] = set()
            for citation in res.citations:
                if citation.get("kind") != "chunk":
                    continue
                cid = int(citation.get("chunk_id"))
                if cid in seen:
                    continue
                chunk_ids.append(cid)
                seen.add(cid)
            corpus_ids: list[str] = []
            seen_corpus: set[str] = set()
            for cid in chunk_ids:
                doc_id = chunk_to_doc.get(cid)
                if doc_id is None:
                    continue
                for corpus_id in doc_to_corpus.get(doc_id, []):
                    if corpus_id in seen_corpus:
                        continue
                    corpus_ids.append(corpus_id)
                    seen_corpus.add(corpus_id)
            per_query_retrieved[q.qid] = corpus_ids

        scores = score_run(
            per_query_retrieved=per_query_retrieved,
            per_query_qrels=qrels,
            ks=(1, 5, 10, 32),
            ndcg_k=10,
        )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as fh:
            for q, res in zip(queries, results):
                fh.write(
                    json.dumps(
                        {
                            "discipline": q.discipline,
                            "qid": q.qid,
                            "lang": lang,
                            "retrieved_corpus_ids": per_query_retrieved.get(q.qid, []),
                            **res.to_jsonl(),
                        }
                    )
                    + "\n"
                )

        metrics = scores.to_dict()
        metrics["lang"] = lang
        metrics["disciplines"] = disciplines

        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_queries": len(queries),
                "lang": lang,
                "disciplines": disciplines,
                "concurrency": concurrency,
                "provider_model": ctx.provider_model,
                "ingest_settings": ingest_settings,
            },
        )
        manifest_path = run_dir / "run_artifact.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "suite": self.suite,
                    "benchmark": self.name,
                    "raw_path": "raw.jsonl",
                    "metrics": metrics,
                    "extra": artifact.extra,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return artifact

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="CUREv1 — single-arm SurfSense retrieval",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        recall = m.get("recall_at_k", {})
        lines: list[str] = [
            format_ingest_settings_md(latest.extra.get("ingest_settings")),
            f"- Language: {m.get('lang', '?')}",
            f"- Disciplines: {', '.join(m.get('disciplines', []) or ['?'])}",
            f"- n_queries (after qrels intersection): {m.get('n_queries', 0)}",
        ]
        for k in (1, 5, 10, 32):
            v = recall.get(str(k), recall.get(k))
            if v is not None:
                lines.append(f"- Recall@{k}: {float(v):.3f}")
        lines.append(f"- MRR: {float(m.get('mrr', 0.0)):.3f}")
        lines.append(f"- nDCG@10: {float(m.get('ndcg_at_10', 0.0)):.3f}")
        return ReportSection(
            title="CUREv1 — single-arm SurfSense retrieval",
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


__all__ = ["CureBenchmark", "CureQuery"]
