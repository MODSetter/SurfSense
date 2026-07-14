"""MedXpertQA-MM runner — Native PDF (vision) vs SurfSense (vision RAG).

Headline benchmark for the medical suite.

* Native arm reads the rendered PDF (case + images + options) via
  OpenRouter ``chat/completions`` + the file-parser plugin.
* SurfSense arm queries ``POST /api/v1/new_chat`` scoped via
  ``mentioned_document_ids=[doc_id]`` to the same per-question PDF.

Operational notes:

* PDFs contain real images (radiology, dermoscopy, pathology, ECGs).
  Operator must pin a vision-capable model via
  ``setup --provider-model anthropic/claude-sonnet-4.5`` (or similar);
  the runner emits a warning if a known text-only slug is pinned.
* MedXpertQA tags ``medical_task`` (Diagnosis / Treatment / Basic
  Medicine) and ``body_system`` (Cardiovascular / Lymphatic / …)
  directly on every row; we slice the report by both.
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
from ....core.providers.openrouter_pdf import OpenRouterPdfProvider, PdfEngine
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
)
from ....core.scenarios import format_scenario_md
from .prompt import ANSWER_LETTERS, build_prompt

logger = logging.getLogger(__name__)


_TEXT_ONLY_HINTS = ("gpt-5.4-mini", "gpt-3.5", "text-only", "instruct-")


@dataclass
class MXQuestion:
    qid: str
    question: str
    options: dict[str, str]
    label: str
    medical_task: str
    body_system: str
    question_type: str
    split: str
    n_images: int
    pdf_path: Path
    document_id: int | None


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
            rows[str(row["qid"])] = row
    return rows, settings


def _load_questions(
    questions_jsonl: Path,
    doc_map: dict[str, dict[str, Any]],
    *,
    split_filter: str | None,
    task_filter: str | None,
    body_filter: str | None,
    require_images: bool,
    sample_n: int | None,
) -> list[MXQuestion]:
    out: list[MXQuestion] = []
    with questions_jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            qid = str(row.get("qid") or "").strip()
            if not qid:
                continue
            if split_filter and split_filter != "all" and row.get("split") != split_filter:
                continue
            if task_filter and task_filter != "all" and row.get("medical_task") != task_filter:
                continue
            if body_filter and body_filter != "all" and row.get("body_system") != body_filter:
                continue
            map_row = doc_map.get(qid)
            if map_row is None:
                logger.debug("No doc-map entry for %s; skipping", qid)
                continue
            n_images = int(map_row.get("n_images", 0))
            if require_images and n_images <= 0:
                continue
            out.append(
                MXQuestion(
                    qid=qid,
                    question=str(row.get("question") or ""),
                    options={str(k).upper(): str(v) for k, v in (row.get("options") or {}).items()},
                    label=str(row.get("label") or "").strip().upper(),
                    medical_task=str(row.get("medical_task") or "").strip(),
                    body_system=str(row.get("body_system") or "").strip(),
                    question_type=str(row.get("question_type") or "").strip(),
                    split=str(row.get("split") or ""),
                    n_images=n_images,
                    pdf_path=Path(map_row["pdf_path"]),
                    document_id=map_row.get("document_id"),
                )
            )
    out.sort(key=lambda q: (q.split, q.qid))
    if sample_n is not None and sample_n > 0:
        out = out[:sample_n]
    return out


async def _gather_with_limit(coros: Iterable, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(coro):
        async with sem:
            return await coro

    return await asyncio.gather(*(_wrap(c) for c in coros))


_DESCRIPTION = (
    "MedXpertQA-MM (~2,000 multimodal medical exam questions, 5 options, with images) — "
    "Native PDF (vision) vs SurfSense (vision RAG) head-to-head."
)

# MedXpertQA-MM PDFs embed clinical images; vision LLM at ingest is
# the whole point. Operators can flip ``--no-vision-llm`` to measure
# how much we degrade without it (likely material).
_DEFAULT_INGEST_SETTINGS = IngestSettings(
    use_vision_llm=True,
    processing_mode="basic",
)


class MedXpertQAMMBenchmark:
    """Multimodal medical exam head-to-head."""

    suite: str = "medical"
    name: str = "medxpertqa"
    headline: bool = True  # The medical suite headline.
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--split",
            default="test",
            choices=["test", "dev", "all"],
            help="Which MedXpertQA-MM split to run (default: test).",
        )
        parser.add_argument(
            "--task",
            default="all",
            help="Filter by medical_task value (e.g. Diagnosis, Treatment, Basic Medicine).",
        )
        parser.add_argument(
            "--body-system",
            dest="body_filter",
            default="all",
            help="Filter by body_system value (e.g. Cardiovascular, Lymphatic).",
        )
        parser.add_argument(
            "--require-images",
            dest="require_images",
            action="store_true",
            help="Skip rare MM rows that ended up with zero resolvable images.",
        )
        parser.add_argument(
            "--n",
            dest="sample_n",
            type=int,
            default=None,
            help="Run only the first N questions after filters apply.",
        )
        parser.add_argument(
            "--concurrency", type=int, default=4, help="Parallel question workers per arm."
        )
        parser.add_argument(
            "--no-mentions",
            dest="no_mentions",
            action="store_true",
            help="SurfSense arm: skip mentioned_document_ids (unscoped retrieval).",
        )
        parser.add_argument(
            "--pdf-engine",
            default="native",
            choices=[e.value for e in PdfEngine],
            help="OpenRouter file-parser engine for the native arm.",
        )
        parser.add_argument(
            "--max-output-tokens",
            type=int,
            default=512,
            help="Cap on completion length for both arms.",
        )
        # Ingest-only knobs (forwarded by the CLI to ingest.run_ingest).
        parser.add_argument(
            "--max-questions",
            dest="max_questions",
            type=int,
            default=None,
            help="(ingest only) cap on number of MM questions to render + upload.",
        )
        parser.add_argument(
            "--upload-batch-size",
            dest="upload_batch_size",
            type=int,
            default=8,
            help="(ingest only) PDFs per fileupload call.",
        )
        parser.add_argument(
            "--skip-upload",
            dest="skip_upload",
            action="store_true",
            help="(ingest only) render PDFs locally but don't push to SurfSense.",
        )
        parser.add_argument(
            "--include-dev",
            dest="include_dev",
            action="store_true",
            help="(ingest only) shorthand for --split all.",
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
            split=opts.get("split") or "test",
            max_questions=opts.get("max_questions"),
            upload_batch_size=int(opts.get("upload_batch_size") or 8),
            skip_upload=bool(opts.get("skip_upload", False)),
            include_dev=bool(opts.get("include_dev", False)),
            settings=settings,
        )

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        split_filter = opts.get("split") or "test"
        task_filter = opts.get("task") or "all"
        body_filter = opts.get("body_filter") or "all"
        require_images = bool(opts.get("require_images"))
        sample_n = opts.get("sample_n")
        concurrency = int(opts.get("concurrency") or 4)
        no_mentions = bool(opts.get("no_mentions"))
        pdf_engine_name = opts.get("pdf_engine") or "native"
        max_output_tokens = int(opts.get("max_output_tokens") or 512)

        bench_dir = ctx.benchmark_data_dir()
        questions_jsonl = bench_dir / "questions.jsonl"
        map_path = ctx.maps_dir() / "medxpertqa_doc_map.jsonl"
        if not questions_jsonl.exists() or not map_path.exists():
            raise RuntimeError(
                "MedXpertQA-MM not ingested for this suite. Run "
                "`python -m surfsense_evals ingest medical medxpertqa` first."
            )

        doc_map, ingest_settings = _load_doc_map(map_path)
        questions = _load_questions(
            questions_jsonl,
            doc_map,
            split_filter=split_filter,
            task_filter=task_filter if task_filter != "all" else None,
            body_filter=body_filter if body_filter != "all" else None,
            require_images=require_images,
            sample_n=sample_n,
        )
        if not questions:
            raise RuntimeError(
                "No MedXpertQA-MM questions matched the filters; broaden --split/--task/--body-system/--n."
            )
        logger.info("MedXpertQA-MM: scheduled %d questions", len(questions))

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY env var is required for the native arm.")

        # Native arm slug differs from SurfSense slug only in cost-arbitrage
        # scenario; otherwise both arms answer with provider_model.
        native_arm_model = ctx.native_arm_model
        if any(hint in native_arm_model.lower() for hint in _TEXT_ONLY_HINTS):
            if ctx.scenario == "symmetric-cheap":
                logger.info(
                    "symmetric-cheap: native arm pinned to text-only %r as "
                    "intended; expect it to lose on image-bearing questions "
                    "(SurfSense answers from vision-extracted chunks).",
                    native_arm_model,
                )
            else:
                logger.warning(
                    "Native arm slug %r looks text-only; image content in "
                    "MedXpertQA PDFs will be ignored. Re-pin via "
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

        async def _native_one(q: MXQuestion) -> ArmResult:
            return await native_arm.answer(_make_native_request(q, max_output_tokens))

        async def _surf_one(q: MXQuestion) -> ArmResult:
            return await surf_arm.answer(_make_surfsense_request(q, no_mentions=no_mentions))

        native_results, surf_results = await asyncio.gather(
            _gather_with_limit((_native_one(q) for q in questions), concurrency=concurrency),
            _gather_with_limit((_surf_one(q) for q in questions), concurrency=concurrency),
        )

        with raw_path.open("w", encoding="utf-8") as fh:
            for q, n_res, s_res in zip(questions, native_results, surf_results, strict=False):
                meta = {
                    "qid": q.qid,
                    "split": q.split,
                    "medical_task": q.medical_task,
                    "body_system": q.body_system,
                    "question_type": q.question_type,
                    "n_images": q.n_images,
                    "correct": q.label,
                    "document_id": q.document_id,
                }
                fh.write(json.dumps({**meta, **n_res.to_jsonl()}) + "\n")
                fh.write(json.dumps({**meta, **s_res.to_jsonl()}) + "\n")

        metrics = _compute_metrics(questions, native_results, surf_results)
        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_questions": len(questions),
                "concurrency": concurrency,
                "split_filter": split_filter,
                "task_filter": task_filter,
                "body_filter": body_filter,
                "require_images": require_images,
                "no_mentions": no_mentions,
                "pdf_engine": pdf_engine_name,
                "scenario": ctx.scenario,
                "provider_model": ctx.provider_model,
                "native_arm_model": native_arm_model,
                "vision_provider_model": ctx.vision_provider_model,
                "chat_model_id": ctx.chat_model_id,
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
                title="MedXpertQA-MM — Native PDF (vision) vs SurfSense (vision RAG)",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        native = m.get("native", {})
        surf = m.get("surfsense", {})
        delta = m.get("delta", {})
        per_task = m.get("per_task", {})
        per_body = m.get("per_body_system", {})
        extra = latest.extra

        body_lines: list[str] = []
        body_lines.append(
            f"- Sample size: {extra.get('n_questions', '?')} questions "
            f"(split: `{extra.get('split_filter', 'test')}`, "
            f"task: `{extra.get('task_filter', 'all')}`, "
            f"body: `{extra.get('body_filter', 'all')}`, "
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
            f"  - Bootstrap 95% CI on delta: "
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
        if per_task:
            body_lines.append("- Per-medical_task split:")
            for task_name, vals in sorted(per_task.items()):
                body_lines.append(
                    f"  - {task_name}: SurfSense {_pp(vals.get('delta_accuracy_pp'))} pp "
                    f"(n={vals.get('n')})"
                )
        if per_body:
            body_lines.append("- Per-body_system split (top 5 by sample size):")
            top = sorted(per_body.items(), key=lambda kv: -kv[1].get("n", 0))[:5]
            for body_name, vals in top:
                body_lines.append(
                    f"  - {body_name}: SurfSense {_pp(vals.get('delta_accuracy_pp'))} pp "
                    f"(n={vals.get('n')})"
                )

        return ReportSection(
            title="MedXpertQA-MM — Native PDF (vision) vs SurfSense (vision RAG)",
            headline=False,
            body_md="\n".join(body_lines),
            body_json=m,
        )


# ---------------------------------------------------------------------------
# Per-question helpers
# ---------------------------------------------------------------------------


def _make_native_request(q: MXQuestion, max_tokens: int) -> ArmRequest:
    prompt = build_prompt(q.question, q.options)
    return ArmRequest(
        question_id=q.qid,
        prompt=prompt,
        pdf_paths=[q.pdf_path],
        options={"max_tokens": max_tokens},
    )


def _make_surfsense_request(q: MXQuestion, *, no_mentions: bool) -> ArmRequest:
    prompt = build_prompt(q.question, q.options)
    mentions: list[int] | None = None
    if not no_mentions and q.document_id is not None:
        mentions = [int(q.document_id)]
    return ArmRequest(
        question_id=q.qid,
        prompt=prompt,
        mentioned_document_ids=mentions,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _compute_metrics(
    questions: list[MXQuestion],
    native_results: list[ArmResult],
    surf_results: list[ArmResult],
) -> dict[str, Any]:
    native_correct: list[bool] = []
    surf_correct: list[bool] = []
    for q, n_res, s_res in zip(questions, native_results, surf_results, strict=False):
        gold = q.label
        n_ok = (n_res.answer_letter or "").upper() == gold and gold in ANSWER_LETTERS
        s_ok = (s_res.answer_letter or "").upper() == gold and gold in ANSWER_LETTERS
        native_correct.append(n_ok)
        surf_correct.append(s_ok)

    native_costs = [float(r.cost_micros) for r in native_results]
    surf_costs = [float(r.cost_micros) for r in surf_results]
    native_lats = [float(r.latency_ms) for r in native_results]
    surf_lats = [float(r.latency_ms) for r in surf_results]
    native_in = [float(r.input_tokens) for r in native_results]
    native_out = [float(r.output_tokens) for r in native_results]

    native_acc = accuracy_with_wilson_ci(sum(native_correct), len(native_correct))
    surf_acc = accuracy_with_wilson_ci(sum(surf_correct), len(surf_correct))
    mc = mcnemar_test(native_correct, surf_correct)
    boot = bootstrap_delta_ci(native_correct, surf_correct, n_resamples=2000)

    native_cost_agg = paired_aggregate(native_costs)
    surf_cost_agg = paired_aggregate(surf_costs)
    native_lat_agg = paired_aggregate(native_lats)
    surf_lat_agg = paired_aggregate(surf_lats)

    cost_pct = _safe_pct(surf_cost_agg.mean, native_cost_agg.mean)
    lat_pct = _safe_pct(surf_lat_agg.median, native_lat_agg.median)

    per_task = _per_field(
        questions, native_correct, surf_correct, key=lambda q: q.medical_task or "unknown"
    )
    per_body = _per_field(
        questions, native_correct, surf_correct, key=lambda q: q.body_system or "unknown"
    )

    return {
        "native": {
            **native_acc.to_dict(),
            "cost_micros_mean": native_cost_agg.mean,
            "cost_micros_median": native_cost_agg.median,
            "latency_ms_mean": native_lat_agg.mean,
            "latency_ms_median": native_lat_agg.median,
            "latency_ms_p95": native_lat_agg.p95,
            "input_tokens_mean": (sum(native_in) / len(native_in)) if native_in else 0.0,
            "output_tokens_mean": (sum(native_out) / len(native_out)) if native_out else 0.0,
        },
        "surfsense": {
            **surf_acc.to_dict(),
            "cost_micros_mean": surf_cost_agg.mean,
            "cost_micros_median": surf_cost_agg.median,
            "latency_ms_mean": surf_lat_agg.mean,
            "latency_ms_median": surf_lat_agg.median,
            "latency_ms_p95": surf_lat_agg.p95,
        },
        "delta": {
            "accuracy_pp": 100.0 * (surf_acc.accuracy - native_acc.accuracy),
            "mcnemar_p_value": mc.p_value,
            "mcnemar_method": mc.method,
            "mcnemar_b_native_only": mc.b,
            "mcnemar_c_surfsense_only": mc.c,
            "bootstrap_ci_low": 100.0 * boot.ci_low,
            "bootstrap_ci_high": 100.0 * boot.ci_high,
            "cost_micros_pct": cost_pct,
            "latency_ms_pct": lat_pct,
        },
        "per_task": per_task,
        "per_body_system": per_body,
    }


def _per_field(
    questions: list[MXQuestion],
    native_correct: list[bool],
    surf_correct: list[bool],
    *,
    key,
) -> dict[str, dict[str, Any]]:
    bucket: dict[str, list[tuple[bool, bool]]] = {}
    for q, n_ok, s_ok in zip(questions, native_correct, surf_correct, strict=False):
        bucket.setdefault(key(q), []).append((n_ok, s_ok))
    out: dict[str, dict[str, Any]] = {}
    for k, pairs in bucket.items():
        n_correct = [a for a, _ in pairs]
        s_correct = [b for _, b in pairs]
        out[k] = {
            "n": len(pairs),
            "native_accuracy": (sum(n_correct) / len(pairs)) if pairs else 0.0,
            "surfsense_accuracy": (sum(s_correct) / len(pairs)) if pairs else 0.0,
            "delta_accuracy_pp": (
                100.0 * (sum(s_correct) - sum(n_correct)) / len(pairs) if pairs else 0.0
            ),
        }
    return out


def _safe_pct(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return 100.0 * (numerator - denominator) / denominator


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _arm_summary_lines(d: dict[str, Any], *, indent: str) -> str:
    if not d:
        return f"{indent}(no data)"
    acc = d.get("accuracy", 0.0)
    low = d.get("ci_low", 0.0)
    high = d.get("ci_high", 0.0)
    lines = [
        f"{indent}- Accuracy: {acc * 100:.1f}% (Wilson 95% CI: {low * 100:.1f}% – {high * 100:.1f}%)",
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


__all__ = ["MedXpertQAMMBenchmark", "MXQuestion"]
