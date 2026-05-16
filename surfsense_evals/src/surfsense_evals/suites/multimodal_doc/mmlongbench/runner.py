"""MMLongBench-Doc runner — head-to-head Native PDF (vision) vs SurfSense (vision RAG).

Differences from a typical MCQ head-to-head:

* Open-ended answers (Str / Int / Float / List / Not-answerable) — uses
  ``extract_freeform_answer`` instead of ``extract_answer_letter``.
* Format-aware grader (see ``.grader``) returns both binary correctness
  (for accuracy / McNemar) and continuous F1 (for nuanced reporting).
* Native arm requires a vision-capable model — we don't enforce this
  in code (operator's choice via ``setup --provider-model``) but we
  emit a warning if the pinned slug looks text-only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.arms import ArmRequest, ArmResult, NativePdfArm, SurfSenseArm
from ....core.config import utc_iso_timestamp
from ....core.ingest_settings import (
    IngestSettings,
    add_ingest_settings_args,
    format_ingest_settings_md,
    is_settings_header,
)
from ....core.metrics.comparison import (
    bootstrap_delta_ci,
    mcnemar_test,
    paired_aggregate,
)
from ....core.metrics.mc_accuracy import accuracy_with_wilson_ci
from ....core.parse.freeform_answer import extract_freeform_answer
from ....core.providers.openrouter_pdf import OpenRouterPdfProvider, PdfEngine
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
)
from ....core.scenarios import format_scenario_md
from .grader import GradeResult, grade
from .prompt import build_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Question + map row shapes
# ---------------------------------------------------------------------------


@dataclass
class MMLBQuestion:
    qid: str               # synthesised from doc_id + index
    doc_id: str            # filename inside the documents/ folder
    doc_type: str
    question: str
    gold_answer: str
    answer_format: str
    evidence_pages: list[int]
    evidence_sources: list[str]
    pdf_path: Path
    document_id: int | None  # SurfSense doc id (None if upload skipped)


def _load_doc_map(map_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Read the doc map JSONL.

    Returns ``(rows, settings)`` where ``settings`` is the
    ``__settings__`` header blob (or ``{}`` for legacy maps).
    """

    rows: dict[str, dict[str, Any]] = {}
    settings: dict[str, Any] = {}
    with map_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if is_settings_header(row):
                settings = dict(row["__settings__"])
                continue
            rows[str(row["doc_id"])] = row
    return rows, settings


def _load_questions(
    questions_jsonl: Path,
    doc_map: dict[str, dict[str, Any]],
    *,
    doc_filter: list[str] | None,
    format_filter: str | None,
    sample_n: int | None,
    skip_unanswerable: bool,
) -> list[MMLBQuestion]:
    out: list[MMLBQuestion] = []
    per_doc_counter: dict[str, int] = {}
    with questions_jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            doc_id = str(row.get("doc_id") or "").strip()
            if not doc_id:
                continue
            if doc_filter and doc_id not in doc_filter:
                continue
            map_row = doc_map.get(doc_id)
            if map_row is None:
                logger.debug("No doc-map entry for %s; skipping", doc_id)
                continue
            answer_format = str(row.get("answer_format") or "").strip().lower()
            if format_filter and format_filter != "all" and format_filter != answer_format:
                continue
            gold = str(row.get("answer") or "").strip()
            if skip_unanswerable and answer_format == "none":
                continue
            idx = per_doc_counter.get(doc_id, 0)
            per_doc_counter[doc_id] = idx + 1
            out.append(MMLBQuestion(
                qid=f"{doc_id}::Q{idx:03d}",
                doc_id=doc_id,
                doc_type=str(row.get("doc_type") or "").strip(),
                question=str(row.get("question") or "").strip(),
                gold_answer=gold,
                answer_format=answer_format,
                evidence_pages=list(row.get("evidence_pages") or []),
                evidence_sources=list(row.get("evidence_sources") or []),
                pdf_path=Path(map_row["pdf_path"]),
                document_id=map_row.get("document_id"),
            ))
    out.sort(key=lambda q: (q.doc_id, q.qid))
    if sample_n is not None and sample_n > 0:
        out = out[:sample_n]
    return out


# ---------------------------------------------------------------------------
# Bounded concurrency helper
# ---------------------------------------------------------------------------


async def _gather_with_limit(coros: Iterable, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(coro):
        async with sem:
            return await coro

    return await asyncio.gather(*(_wrap(c) for c in coros))


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


_DESCRIPTION = (
    "MMLongBench-Doc (135 long PDFs, 1,091 multimodal questions) — "
    "Native PDF (vision) vs SurfSense (vision RAG) head-to-head."
)


_TEXT_ONLY_HINTS = ("gpt-5.4-mini", "gpt-3.5", "text-only", "instruct-")

# MMLongBench-Doc PDFs are long documents with figures, charts, and
# tables. Vision LLM at ingest is the whole point; flip --no-vision-llm
# to measure how much SurfSense degrades on real document images.
_DEFAULT_INGEST_SETTINGS = IngestSettings(
    use_vision_llm=True,
    processing_mode="basic",
    should_summarize=False,
)


class MMLongBenchDocBenchmark:
    """Long-document multimodal RAG vs native vision."""

    suite: str = "multimodal_doc"
    name: str = "mmlongbench"
    headline: bool = True
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--docs",
            default=None,
            help="Comma-separated doc_ids (filenames) to run (default: all).",
        )
        parser.add_argument(
            "--format",
            default="all",
            choices=["all", "str", "int", "float", "list", "none"],
            help="Filter to one answer format. 'none' = unanswerable probes only.",
        )
        parser.add_argument(
            "--n", dest="sample_n", type=int, default=None,
            help="Run only the first N questions after filters apply.",
        )
        parser.add_argument(
            "--skip-unanswerable", dest="skip_unanswerable", action="store_true",
            help="Drop ~22%% unanswerable questions (use to compare against baselines that don't include them).",
        )
        parser.add_argument(
            "--concurrency", type=int, default=4,
            help="Parallel question workers per arm.",
        )
        parser.add_argument(
            "--no-mentions", dest="no_mentions", action="store_true",
            help="SurfSense arm: skip mentioned_document_ids (unscoped retrieval).",
        )
        parser.add_argument(
            "--pdf-engine", default="native",
            choices=[e.value for e in PdfEngine],
            help="OpenRouter file-parser engine for the native arm.",
        )
        parser.add_argument(
            "--max-output-tokens", type=int, default=512,
            help="Cap on completion length for both arms.",
        )
        # Ingest-only knobs (forwarded by the CLI to ingest.run_ingest).
        parser.add_argument(
            "--max-docs", dest="max_docs", type=int, default=None,
            help="(ingest only) cap on number of unique PDFs to download + upload.",
        )
        parser.add_argument(
            "--upload-batch-size", dest="upload_batch_size", type=int, default=8,
            help="(ingest only) PDFs per fileupload call.",
        )
        parser.add_argument(
            "--skip-upload", dest="skip_upload", action="store_true",
            help="(ingest only) cache PDFs locally but don't push to SurfSense.",
        )
        # Per-upload knobs forwarded to /documents/fileupload at ingest;
        # ignored at run-time (runner reads the resolved settings out of
        # the doc-map manifest header).
        add_ingest_settings_args(parser, defaults=_DEFAULT_INGEST_SETTINGS)

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest

        settings = IngestSettings.merge(_DEFAULT_INGEST_SETTINGS, opts)
        await run_ingest(
            ctx,
            max_docs=opts.get("max_docs"),
            upload_batch_size=int(opts.get("upload_batch_size") or 8),
            skip_upload=bool(opts.get("skip_upload", False)),
            settings=settings,
        )

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        docs_raw: str | None = opts.get("docs")
        doc_filter = [d.strip() for d in docs_raw.split(",")] if docs_raw else None
        format_filter = opts.get("format") or "all"
        sample_n = opts.get("sample_n")
        skip_unanswerable = bool(opts.get("skip_unanswerable"))
        concurrency = int(opts.get("concurrency") or 4)
        no_mentions = bool(opts.get("no_mentions"))
        pdf_engine_name = opts.get("pdf_engine") or "native"
        max_output_tokens = int(opts.get("max_output_tokens") or 512)

        bench_dir = ctx.benchmark_data_dir()
        questions_jsonl = bench_dir / "questions.jsonl"
        map_path = ctx.maps_dir() / "mmlongbench_doc_map.jsonl"
        if not questions_jsonl.exists() or not map_path.exists():
            raise RuntimeError(
                "MMLongBench-Doc not ingested for this suite. Run "
                "`python -m surfsense_evals ingest multimodal_doc mmlongbench` first."
            )

        doc_map, ingest_settings = _load_doc_map(map_path)
        questions = _load_questions(
            questions_jsonl, doc_map,
            doc_filter=doc_filter,
            format_filter=None if format_filter == "all" else format_filter,
            sample_n=sample_n,
            skip_unanswerable=skip_unanswerable,
        )
        if not questions:
            raise RuntimeError(
                "No MMLongBench questions matched the filters; broaden --docs/--format/--n."
            )
        logger.info("MMLongBench-Doc: scheduled %d questions", len(questions))

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY env var is required for the native arm."
            )

        # Native arm slug differs from SurfSense slug only in cost-arbitrage
        # scenario; otherwise both arms answer with provider_model.
        native_arm_model = ctx.native_arm_model
        if any(hint in native_arm_model.lower() for hint in _TEXT_ONLY_HINTS):
            if ctx.scenario == "symmetric-cheap":
                logger.info(
                    "symmetric-cheap: native arm pinned to text-only %r as "
                    "intended; expect it to lose on image-bearing pages "
                    "(SurfSense answers from vision-extracted chunks).",
                    native_arm_model,
                )
            else:
                logger.warning(
                    "Native arm slug %r looks text-only; image content in "
                    "PDFs will be ignored. Re-pin via "
                    "`setup --provider-model anthropic/claude-sonnet-4.5` "
                    "(or pass --native-arm-model and --scenario cost-arbitrage "
                    "to make this asymmetry explicit).",
                    native_arm_model,
                )

        provider = OpenRouterPdfProvider(
            api_key=api_key,
            base_url=ctx.config.openrouter_base_url,
            model=native_arm_model,
            engine=PdfEngine(pdf_engine_name),
        )
        native_arm = NativePdfArm(provider=provider, max_output_tokens=max_output_tokens)
        surf_arm = SurfSenseArm(
            client=ctx.new_chat_client(),
            search_space_id=ctx.search_space_id,
            ephemeral_threads=True,
        )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"

        async def _native_one(q: MMLBQuestion) -> ArmResult:
            return await native_arm.answer(_make_native_request(q, max_output_tokens))

        async def _surf_one(q: MMLBQuestion) -> ArmResult:
            return await surf_arm.answer(_make_surfsense_request(q, no_mentions=no_mentions))

        native_results, surf_results = await asyncio.gather(
            _gather_with_limit((_native_one(q) for q in questions), concurrency=concurrency),
            _gather_with_limit((_surf_one(q) for q in questions), concurrency=concurrency),
        )

        native_grades = [_grade_one(q, r) for q, r in zip(questions, native_results, strict=False)]
        surf_grades = [_grade_one(q, r) for q, r in zip(questions, surf_results, strict=False)]

        with raw_path.open("w", encoding="utf-8") as fh:
            for q, n_res, s_res, n_g, s_g in zip(
                questions, native_results, surf_results, native_grades, surf_grades, strict=False
            ):
                meta = {
                    "qid": q.qid,
                    "doc_id": q.doc_id,
                    "doc_type": q.doc_type,
                    "answer_format": q.answer_format,
                    "gold": q.gold_answer,
                    "evidence_pages": q.evidence_pages,
                    "evidence_sources": q.evidence_sources,
                    "document_id": q.document_id,
                }
                fh.write(json.dumps({
                    **meta,
                    **n_res.to_jsonl(),
                    "graded": _grade_to_jsonl(n_g),
                }) + "\n")
                fh.write(json.dumps({
                    **meta,
                    **s_res.to_jsonl(),
                    "graded": _grade_to_jsonl(s_g),
                }) + "\n")

        metrics = _compute_metrics(questions, native_results, surf_results, native_grades, surf_grades)
        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_questions": len(questions),
                "concurrency": concurrency,
                "format_filter": format_filter,
                "skip_unanswerable": skip_unanswerable,
                "no_mentions": no_mentions,
                "pdf_engine": pdf_engine_name,
                "scenario": ctx.scenario,
                "provider_model": ctx.provider_model,
                "native_arm_model": native_arm_model,
                "vision_provider_model": ctx.vision_provider_model,
                "agent_llm_id": ctx.agent_llm_id,
                "ingest_settings": ingest_settings,
            },
        )

        manifest_path = run_dir / "run_artifact.json"
        manifest_path.write_text(
            json.dumps({
                "suite": self.suite,
                "benchmark": self.name,
                "raw_path": "raw.jsonl",
                "metrics": metrics,
                "extra": artifact.extra,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="MMLongBench-Doc — Native PDF (vision) vs SurfSense (vision RAG)",
                headline=True,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        native = m.get("native", {})
        surf = m.get("surfsense", {})
        delta = m.get("delta", {})
        per_format = m.get("per_format", {})
        extra = latest.extra

        body_lines: list[str] = []
        body_lines.append(
            f"- Sample size: {extra.get('n_questions', '?')} questions "
            f"(format filter: `{extra.get('format_filter', 'all')}`, "
            f"skip-unanswerable: `{extra.get('skip_unanswerable', False)}`, "
            f"engine: `{extra.get('pdf_engine', 'native')}`)."
        )
        body_lines.append(format_scenario_md(extra))
        body_lines.append(format_ingest_settings_md(extra.get("ingest_settings")))
        body_lines.append(
            "- Native arm (OpenRouter `chat/completions` + file plugin, "
            f"`{extra.get('native_arm_model') or extra.get('provider_model', '?')}`):"
        )
        body_lines.append(_arm_summary_lines(native, indent="  "))
        body_lines.append(
            "- SurfSense arm (`POST /api/v1/new_chat`, vision RAG over chunks, "
            f"`{extra.get('provider_model', '?')}`):"
        )
        body_lines.append(_arm_summary_lines(surf, indent="  "))
        body_lines.append("- Delta (paired):")
        body_lines.append(
            f"  - Accuracy: SurfSense {_pp(delta.get('accuracy_pp'))} pp "
            f"(McNemar p={_fmt(delta.get('mcnemar_p_value'), 4)}, "
            f"method={delta.get('mcnemar_method')})"
        )
        body_lines.append(
            f"  - F1 (mean): SurfSense {_pp(delta.get('f1_pp'))} pp"
        )
        body_lines.append(
            f"  - Bootstrap 95% CI on accuracy delta: "
            f"[{_pp(delta.get('bootstrap_ci_low'))}pp, {_pp(delta.get('bootstrap_ci_high'))}pp]"
        )
        body_lines.append(
            f"  - Cost / question: native ${_dollars(native.get('cost_micros_mean'))}, "
            f"surfsense ${_dollars(surf.get('cost_micros_mean'))} "
            f"(SurfSense delta {_pct_change(delta.get('cost_micros_pct'))})"
        )
        body_lines.append(
            f"  - Latency p50: native {_ms_to_s(native.get('latency_ms_median'))}, "
            f"surfsense {_ms_to_s(surf.get('latency_ms_median'))} "
            f"(SurfSense delta {_pct_change(delta.get('latency_ms_pct'))})"
        )
        if per_format:
            body_lines.append("- Per-format split (accuracy delta in pp):")
            for fmt, vals in sorted(per_format.items()):
                body_lines.append(
                    f"  - {fmt}: SurfSense {_pp(vals.get('delta_accuracy_pp'))} pp "
                    f"(n={vals.get('n')}, native acc={vals.get('native_accuracy', 0)*100:.1f}%, "
                    f"surf acc={vals.get('surfsense_accuracy', 0)*100:.1f}%)"
                )

        return ReportSection(
            title="MMLongBench-Doc — Native PDF (vision) vs SurfSense (vision RAG)",
            headline=True,
            body_md="\n".join(body_lines),
            body_json=m,
        )


# ---------------------------------------------------------------------------
# Per-question helpers
# ---------------------------------------------------------------------------


def _make_native_request(q: MMLBQuestion, max_tokens: int) -> ArmRequest:
    prompt = build_prompt(q.question, answer_format=q.answer_format)
    return ArmRequest(
        question_id=q.qid,
        prompt=prompt,
        pdf_paths=[q.pdf_path],
        options={"max_tokens": max_tokens},
    )


def _make_surfsense_request(q: MMLBQuestion, *, no_mentions: bool) -> ArmRequest:
    prompt = build_prompt(q.question, answer_format=q.answer_format)
    mentions: list[int] | None = None
    if not no_mentions and q.document_id is not None:
        mentions = [int(q.document_id)]
    return ArmRequest(
        question_id=q.qid,
        prompt=prompt,
        mentioned_document_ids=mentions,
    )


def _grade_one(q: MMLBQuestion, result: ArmResult) -> GradeResult:
    pred_text = extract_freeform_answer(result.raw_text or "")
    return grade(pred=pred_text, gold=q.gold_answer, answer_format=q.answer_format)


def _grade_to_jsonl(g: GradeResult) -> dict[str, Any]:
    return {
        "correct": g.correct,
        "f1": g.f1,
        "method": g.method,
        "normalised_pred": g.normalised_pred,
        "normalised_gold": g.normalised_gold,
    }


# ---------------------------------------------------------------------------
# Metrics aggregation
# ---------------------------------------------------------------------------


def _compute_metrics(
    questions: list[MMLBQuestion],
    native_results: list[ArmResult],
    surf_results: list[ArmResult],
    native_grades: list[GradeResult],
    surf_grades: list[GradeResult],
) -> dict[str, Any]:
    native_correct = [g.correct for g in native_grades]
    surf_correct = [g.correct for g in surf_grades]
    native_f1 = [g.f1 for g in native_grades]
    surf_f1 = [g.f1 for g in surf_grades]

    native_costs = [float(r.cost_micros) for r in native_results]
    surf_costs = [float(r.cost_micros) for r in surf_results]
    native_latencies = [float(r.latency_ms) for r in native_results]
    surf_latencies = [float(r.latency_ms) for r in surf_results]
    native_in_tokens = [float(r.input_tokens) for r in native_results]
    native_out_tokens = [float(r.output_tokens) for r in native_results]

    native_acc = accuracy_with_wilson_ci(sum(native_correct), len(native_correct))
    surf_acc = accuracy_with_wilson_ci(sum(surf_correct), len(surf_correct))
    mc = mcnemar_test(native_correct, surf_correct)
    boot = bootstrap_delta_ci(native_correct, surf_correct, n_resamples=2000)

    native_cost_agg = paired_aggregate(native_costs)
    surf_cost_agg = paired_aggregate(surf_costs)
    native_latency_agg = paired_aggregate(native_latencies)
    surf_latency_agg = paired_aggregate(surf_latencies)

    cost_pct = _safe_pct(surf_cost_agg.mean, native_cost_agg.mean)
    latency_pct = _safe_pct(surf_latency_agg.median, native_latency_agg.median)

    per_format_pairs: dict[str, list[tuple[bool, bool]]] = {}
    for q, n_ok, s_ok in zip(questions, native_correct, surf_correct, strict=False):
        per_format_pairs.setdefault(q.answer_format or "unknown", []).append((n_ok, s_ok))

    per_format: dict[str, dict[str, Any]] = {}
    for fmt, pairs in per_format_pairs.items():
        n_correct = [a for a, _ in pairs]
        s_correct = [b for _, b in pairs]
        per_format[fmt] = {
            "n": len(pairs),
            "native_accuracy": (sum(n_correct) / len(pairs)) if pairs else 0.0,
            "surfsense_accuracy": (sum(s_correct) / len(pairs)) if pairs else 0.0,
            "delta_accuracy_pp": (
                100.0 * (sum(s_correct) - sum(n_correct)) / len(pairs)
                if pairs else 0.0
            ),
        }

    native_f1_mean = sum(native_f1) / len(native_f1) if native_f1 else 0.0
    surf_f1_mean = sum(surf_f1) / len(surf_f1) if surf_f1 else 0.0

    return {
        "native": {
            **native_acc.to_dict(),
            "f1_mean": native_f1_mean,
            "cost_micros_mean": native_cost_agg.mean,
            "cost_micros_median": native_cost_agg.median,
            "latency_ms_mean": native_latency_agg.mean,
            "latency_ms_median": native_latency_agg.median,
            "latency_ms_p95": native_latency_agg.p95,
            "input_tokens_mean": (sum(native_in_tokens) / len(native_in_tokens)) if native_in_tokens else 0.0,
            "output_tokens_mean": (sum(native_out_tokens) / len(native_out_tokens)) if native_out_tokens else 0.0,
        },
        "surfsense": {
            **surf_acc.to_dict(),
            "f1_mean": surf_f1_mean,
            "cost_micros_mean": surf_cost_agg.mean,
            "cost_micros_median": surf_cost_agg.median,
            "latency_ms_mean": surf_latency_agg.mean,
            "latency_ms_median": surf_latency_agg.median,
            "latency_ms_p95": surf_latency_agg.p95,
        },
        "delta": {
            "accuracy_pp": 100.0 * (surf_acc.accuracy - native_acc.accuracy),
            "f1_pp": 100.0 * (surf_f1_mean - native_f1_mean),
            "mcnemar_p_value": mc.p_value,
            "mcnemar_method": mc.method,
            "mcnemar_b_native_only": mc.b,
            "mcnemar_c_surfsense_only": mc.c,
            "bootstrap_ci_low": 100.0 * boot.ci_low,
            "bootstrap_ci_high": 100.0 * boot.ci_high,
            "cost_micros_pct": cost_pct,
            "latency_ms_pct": latency_pct,
        },
        "per_format": per_format,
    }


def _safe_pct(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return 100.0 * (numerator - denominator) / denominator


# ---------------------------------------------------------------------------
# Tiny formatting helpers used by report_section
# ---------------------------------------------------------------------------


def _arm_summary_lines(d: dict[str, Any], *, indent: str) -> str:
    if not d:
        return f"{indent}(no data)"
    acc = d.get("accuracy", 0.0)
    low = d.get("ci_low", 0.0)
    high = d.get("ci_high", 0.0)
    f1 = d.get("f1_mean", 0.0)
    lines = [
        f"{indent}- Accuracy: {acc * 100:.1f}% (Wilson 95% CI: {low * 100:.1f}% – {high * 100:.1f}%)",
        f"{indent}- F1 (token-level mean): {f1 * 100:.1f}%",
        f"{indent}- Cost / question: ${_dollars(d.get('cost_micros_mean'))} (mean), "
        f"${_dollars(d.get('cost_micros_median'))} (median)",
        f"{indent}- Latency: p50 {_ms_to_s(d.get('latency_ms_median'))}, "
        f"p95 {_ms_to_s(d.get('latency_ms_p95'))}",
    ]
    if "input_tokens_mean" in d:
        lines.append(
            f"{indent}- Mean tokens / question: in {d.get('input_tokens_mean', 0):.0f}, "
            f"out {d.get('output_tokens_mean', 0):.0f}"
        )
    return "\n".join(lines)


def _dollars(micros: Any) -> str:
    if micros is None:
        return "?"
    try:
        return f"{(float(micros) / 1_000_000):.4f}"
    except (TypeError, ValueError):
        return "?"


def _ms_to_s(ms: Any) -> str:
    if ms is None:
        return "?"
    try:
        return f"{float(ms) / 1000:.1f}s"
    except (TypeError, ValueError):
        return "?"


def _pp(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):+.1f}"
    except (TypeError, ValueError):
        return "?"


def _pct_change(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):+.0f}%"
    except (TypeError, ValueError):
        return "?"


def _fmt(value: Any, ndigits: int) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return "?"


__all__ = ["MMLBQuestion", "MMLongBenchDocBenchmark"]
