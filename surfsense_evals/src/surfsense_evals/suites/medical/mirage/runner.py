"""MIRAGE runner: SurfSense-only per-task accuracy.

The benchmark file format is one top-level dict per task (``mmlu``,
``medqa``, ``medmcqa``, ``pubmedqa``, ``bioasq``); each task value is
``{question_id: {question, options, answer}}``.

We restrict retrieval to the suite SearchSpace's full corpus (no
``mentioned_document_ids`` — MIRAGE has no per-question ground-truth
document; retrieval *is* the test). Accuracy is paired against the
``answer`` letter from the dataset.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from ....core.arms import ArmRequest, ArmResult, SurfSenseArm
from ....core.config import utc_iso_timestamp
from ....core.ingest_settings import (
    IngestSettings,
    add_ingest_settings_args,
    format_ingest_settings_md,
    read_settings_header,
)
from ....core.metrics.mc_accuracy import accuracy_with_wilson_ci, macro_accuracy
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
)
from .prompt import build_prompt

logger = logging.getLogger(__name__)


_TASKS = ("mmlu", "medqa", "medmcqa", "pubmedqa", "bioasq")
_DESCRIPTION = "MIRAGE (7,663 medical MCQs) — single-arm SurfSense per-task accuracy."

# MIRAGE corpus is text-only (textbook + abstract markdown). Vision
# LLM at ingest is wasted compute by default; flip ``--use-vision-llm``
# to measure cost.
_DEFAULT_INGEST_SETTINGS = IngestSettings(
    use_vision_llm=False,
    processing_mode="basic",
)


@dataclass
class MirageQuestion:
    task: str
    qid: str
    question: str
    options: dict[str, str]
    correct: str

    @property
    def question_id(self) -> str:
        return f"{self.task}::{self.qid}"


def _load_questions(
    benchmark: dict[str, Any],
    *,
    tasks: list[str],
    sample_n: int | None,
) -> list[MirageQuestion]:
    out: list[MirageQuestion] = []
    for task in tasks:
        rows = benchmark.get(task) or {}
        if not isinstance(rows, dict):
            continue
        for qid, raw in rows.items():
            if not isinstance(raw, dict):
                continue
            options = raw.get("options") or {}
            if not isinstance(options, dict):
                continue
            answer_raw = str(raw.get("answer") or "").strip()
            if not answer_raw:
                continue
            answer_letter = answer_raw[:1].upper()
            out.append(
                MirageQuestion(
                    task=task,
                    qid=str(qid),
                    question=str(raw.get("question", "")),
                    options={str(k): str(v) for k, v in options.items() if v},
                    correct=answer_letter,
                )
            )
    out.sort(key=lambda q: (q.task, q.qid))
    if sample_n is not None and sample_n > 0:
        # Stratified-by-task slice so smoke runs cover every task.
        per_task = max(1, sample_n // max(1, len(tasks)))
        sliced: list[MirageQuestion] = []
        per_task_counter: dict[str, int] = {}
        for q in out:
            n = per_task_counter.get(q.task, 0)
            if n >= per_task:
                continue
            sliced.append(q)
            per_task_counter[q.task] = n + 1
            if len(sliced) >= sample_n:
                break
        out = sliced
    return out


async def _gather_with_limit(coros, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(c):
        async with sem:
            return await c

    return await asyncio.gather(*(_wrap(c) for c in coros))


class MirageBenchmark:
    suite: str = "medical"
    name: str = "mirage"
    headline: bool = False
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--task",
            default="all",
            choices=("all", *_TASKS),
            help="Run a single task or all (default: all).",
        )
        parser.add_argument("--n", dest="sample_n", type=int, default=None,
                            help="Stratified sample size across tasks.")
        parser.add_argument("--concurrency", type=int, default=4)
        parser.add_argument(
            "--corpus", default="MedRAG/textbooks",
            help="HF MedRAG corpus to ingest from (default: MedRAG/textbooks).",
        )
        parser.add_argument(
            "--max-snippets-per-task", type=int, default=None,
            help="Cap the per-task ingestion to N snippets (smoke).",
        )
        # Mutually exclusive: by default we skip the upstream 16 GB
        # retrievals zip and ingest the entire corpus. Operators who
        # want the upstream pre-filter pass --use-snippet-filter (and,
        # if their corpus mismatch warrants the 16 GB transfer,
        # --allow-large-download).
        snippet_group = parser.add_mutually_exclusive_group()
        snippet_group.add_argument(
            "--use-snippet-filter", dest="use_snippet_filter", action="store_true",
            default=False,
            help="Download retrieved_snippets_10k.zip (~16 GB) and "
                 "filter the corpus to those ids before ingest. "
                 "Default: skip and ingest entire corpus.",
        )
        snippet_group.add_argument(
            "--skip-snippet-filter", dest="use_snippet_filter", action="store_false",
            help="(Default) Skip the 16 GB upstream zip; ingest entire corpus.",
        )
        parser.add_argument(
            "--allow-large-download", action="store_true", default=False,
            help="Permit downloads larger than 2 GB (e.g. retrieved_snippets_10k.zip).",
        )
        # Per-upload knobs; ignored at run-time (runner reads the
        # resolved settings out of the snippet-map manifest header).
        add_ingest_settings_args(parser, defaults=_DEFAULT_INGEST_SETTINGS)

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest

        settings = IngestSettings.merge(_DEFAULT_INGEST_SETTINGS, opts)
        await run_ingest(
            ctx,
            corpus=str(opts.get("corpus") or "MedRAG/textbooks"),
            max_snippets_per_task=opts.get("max_snippets_per_task"),
            skip_snippet_filter=not bool(opts.get("use_snippet_filter")),
            allow_large_download=bool(opts.get("allow_large_download")),
            settings=settings,
        )

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        task_filter = opts.get("task") or "all"
        tasks = list(_TASKS) if task_filter == "all" else [task_filter]
        sample_n = opts.get("sample_n")
        concurrency = int(opts.get("concurrency") or 4)

        bench_path = ctx.benchmark_data_dir() / "benchmark.json"
        if not bench_path.exists():
            raise RuntimeError(
                "MIRAGE benchmark.json missing. Run "
                "`python -m surfsense_evals ingest medical mirage` first."
            )
        benchmark = json.loads(bench_path.read_text(encoding="utf-8"))
        ingest_settings = read_settings_header(
            ctx.maps_dir() / "mirage_snippet_map.jsonl"
        )
        questions = _load_questions(benchmark, tasks=tasks, sample_n=sample_n)
        if not questions:
            raise RuntimeError(
                f"No MIRAGE questions matched task={task_filter!r} sample_n={sample_n!r}."
            )
        logger.info("MIRAGE: scheduled %d questions across tasks %s",
                    len(questions), tasks)

        arm = SurfSenseArm(
            client=ctx.new_chat_client(),
            search_space_id=ctx.search_space_id,
            ephemeral_threads=True,
        )

        async def _ask(q: MirageQuestion) -> ArmResult:
            request = ArmRequest(
                question_id=q.question_id,
                prompt=build_prompt(q.question, q.options),
            )
            return await arm.answer(request)

        results: list[ArmResult] = await _gather_with_limit(
            (_ask(q) for q in questions), concurrency=concurrency
        )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as fh:
            for q, res in zip(questions, results, strict=False):
                fh.write(
                    json.dumps(
                        {
                            "task": q.task,
                            "qid": q.qid,
                            "correct": q.correct,
                            **res.to_jsonl(),
                        }
                    )
                    + "\n"
                )

        per_task_acc: dict[str, dict[str, Any]] = {}
        for task in tasks:
            n_correct = 0
            n_total = 0
            for q, res in zip(questions, results, strict=False):
                if q.task != task:
                    continue
                n_total += 1
                if (res.answer_letter or "").upper() == q.correct:
                    n_correct += 1
            acc = accuracy_with_wilson_ci(n_correct, n_total)
            per_task_acc[task] = acc.to_dict()

        macro = macro_accuracy(
            {t: accuracy_with_wilson_ci(d["n_correct"], d["n_total"]) for t, d in per_task_acc.items()}
        )
        metrics = {"per_task": per_task_acc, "macro_accuracy": macro}

        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_questions": len(questions),
                "task_filter": task_filter,
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
                title="MIRAGE — single-arm SurfSense per-task accuracy",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        per_task = latest.metrics.get("per_task", {})
        macro = latest.metrics.get("macro_accuracy", 0.0)
        lines: list[str] = []
        lines.append(format_ingest_settings_md(latest.extra.get("ingest_settings")))
        for task in _TASKS:
            row = per_task.get(task)
            if not row:
                continue
            acc = row.get("accuracy", 0.0)
            low = row.get("ci_low", 0.0)
            high = row.get("ci_high", 0.0)
            lines.append(
                f"- {task}: {acc * 100:.1f}% "
                f"(Wilson 95% CI: {low * 100:.1f}% – {high * 100:.1f}%, "
                f"n={row.get('n_total', '?')})"
            )
        if not lines:
            lines.append("- (no per-task results)")
        lines.append(f"- Macro accuracy: {macro * 100:.2f}%")
        return ReportSection(
            title="MIRAGE — single-arm SurfSense per-task accuracy",
            headline=False,
            body_md="\n".join(lines),
            body_json=latest.metrics,
        )


__all__ = ["MirageBenchmark", "MirageQuestion"]
