"""Score a job pack on its real-data cases, per model, so no claim ships before a row backs it.

The cases live with the pack's own content, outside this tree. Keys come from the
environment: ANTHROPIC_API_KEY for anthropic:<id>, OPENROUTER_API_KEY for openrouter:<id>.

    python scripts/run_job_eval.py run --pack <pack dir> --eval <eval dir> \
        --model anthropic:claude-haiku-5-5 --model openrouter:qwen/qwen3.8-27b --runs 3 --out <dir>
    python scripts/run_job_eval.py report <dir>

`--checker <model>` makes the second checks on another model; `--setting key=true` turns on one
of the job's firm settings. Each run writes its filled workbook, or a contract job's redlined
copy, and a JSON record; `report` rolls them up per model.
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from job_eval.cases import Case, load_cases
from job_eval.contract_cases import load_contract_cases
from job_eval.contract_run import run_contract_case
from job_eval.models import model_for
from job_eval.report import report
from job_eval.score import score_case
from job_eval.source_files import source_text
from job_eval.workbook_integrity import integrity_problems

from modules.artifacts.revised_copies.engines import excel
from modules.jobs.evidence.retrieval import Embed
from modules.jobs.evidence.vectors import remembered
from modules.jobs.packs.manifest import read_manifest
from modules.jobs.word_clauses.config import load_config as load_clause_config
from modules.jobs.word_clauses.report import RUNNER as CLAUSES_RUNNER
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.fill import fill_workbook


def run(args: argparse.Namespace) -> None:
    manifest = read_manifest(args.pack)
    if any(job.runner == CLAUSES_RUNNER for job in manifest.jobs):
        _run_contracts(args, manifest)
        return
    cases = load_cases(args.eval, args.case or None)
    if not cases:
        raise SystemExit("No case matched.")
    embed = _embedder(args.embedder)
    for spec in args.model:
        for case in cases:
            job = next(j for j in manifest.jobs if j.key == case.job)
            config = load_config(args.pack / job.config)
            for number in range(1, args.runs + 1):
                _one_run(args, spec, case, config, number, embed)


def _run_contracts(args: argparse.Namespace, manifest) -> None:
    cases = load_contract_cases(args.eval, args.case or None)
    if not cases:
        raise SystemExit("No case matched.")
    embed = _embedder(args.embedder)
    options = {
        "effort": args.effort,
        "reasoning": args.reasoning,
        "embedder": args.embedder,
        "checker": args.checker,
    }
    for spec in args.model:
        for case in cases:
            job = next(j for j in manifest.jobs if j.key == case.job)
            config = load_clause_config(args.pack / job.config)
            settings = config.setting_values(_settings(args.setting))
            for number in range(1, args.runs + 1):
                run_contract_case(
                    args.out,
                    spec,
                    case,
                    config,
                    number,
                    model=_model(args, spec),
                    checker=_model(args, args.checker) if args.checker else None,
                    settings=settings,
                    embed=embed,
                    options=options,
                )


def _model(args: argparse.Namespace, spec: str):
    return model_for(
        spec, concurrency=args.concurrency, effort=args.effort, reasoning=args.reasoning
    )


def _embedder(name: str) -> Embed | None:
    """The app's bundled embedder, as a fresh install searches with; "none" for words alone."""
    if name == "none":
        return None
    # The checkout keeps the bundled model beside the backend; a packaged app ships it so.
    os.environ.setdefault(
        "SURFSENSE_LOCAL_MODELS_DIR",
        str(Path(__file__).resolve().parents[1] / "models"),
    )
    from modules.embedding import encoder
    from modules.embedding.bundled import BGE

    missing = encoder.missing_files(BGE)
    if missing:
        raise SystemExit(
            f"The bundled embedder is not in {os.environ['SURFSENSE_LOCAL_MODELS_DIR']} "
            f"({', '.join(missing)} missing): stage it there, or pass --embedder none."
        )

    def embed(texts: list[str], query: bool) -> list[list[float]]:
        purpose = encoder.Purpose.QUERY if query else encoder.Purpose.DOCUMENT
        return encoder.embed(BGE, texts, purpose)

    # A case's later runs, and later cases over the same policies, reuse the first run's vectors.
    return remembered(embed, f"{BGE.id}@{BGE.weights.sha256}")


def _settings(pairs: list[str] | None) -> dict[str, bool]:
    chosen = {}
    for pair in pairs or ():
        key, _, value = pair.partition("=")
        if value not in ("true", "false"):
            raise SystemExit(f"--setting {pair}: give key=true or key=false.")
        chosen[key] = value == "true"
    return chosen


def _one_run(args, spec: str, case: Case, config, number: int, embed) -> None:
    model = model_for(
        spec, concurrency=args.concurrency, effort=args.effort, reasoning=args.reasoning
    )
    checker = (
        model_for(
            args.checker,
            concurrency=args.concurrency,
            effort=args.effort,
            reasoning=args.reasoning,
        )
        if args.checker
        else None
    )
    chosen = config.setting_values(_settings(args.setting))
    gate = config.statement_gate
    provider_on = bool(gate.provider_setting and chosen.get(gate.provider_setting))
    sources = [source_text(path, index + 1) for index, path in enumerate(case.sources)]
    gold_cells = {(g.sheet.casefold(), g.cell) for g in case.gold}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    named = spec + (f"-checked-{args.checker}" if args.checker else "")
    folder = (
        args.out
        / f"{stamp}-{case.id}-{named.replace(':', '_').replace('/', '_')}-r{number}"
    )
    folder.mkdir(parents=True)
    print(f"{case.id} on {spec}, run {number}: {folder.name}", flush=True)
    started = time.monotonic()
    filled = fill_workbook(
        case.workbook,
        sources,
        config,
        model,
        only=None
        if args.all_rows
        else (lambda row: (row.sheet.casefold(), row.answer_cell) in gold_cells),
        on_row=lambda done, total: print(f"  {done}/{total}", flush=True),
        embed=embed,
        checker=checker,
        settings=chosen,
    )
    out = folder / f"filled{case.workbook.suffix}"
    applied = excel.apply(case.workbook, filled.operations, out)
    writable = {
        (r.row.sheet, cell)
        for r in filled.results
        for cell in (r.row.answer_cell, r.row.comment_cell, r.row.evidence_cell)
        if cell
    }
    scored = score_case(case, filled.results, config, provider_on)
    scored.integrity = (
        integrity_problems(case.workbook, out, writable)
        if applied.saved
        else ["the engine saved nothing: " + applied.as_text()]
    )
    record = {
        "case": case.id,
        "title": case.title,
        "gold_status": case.gold_status,
        "model": spec,
        "checker": args.checker,
        "run": number,
        "started": stamp,
        "seconds": round(time.monotonic() - started, 1),
        "settings": {
            "effort": args.effort,
            "reasoning": args.reasoning,
            "all_rows": args.all_rows,
            "embedder": args.embedder,
            "job": filled.settings,
        },
        "whole_sources": filled.whole_sources,
        "questions_found": len(filled.layout.rows),
        "tables": [t.__dict__ for t in filled.layout.tables],
        "counts": filled.counts,
        "scored_rows": len(scored.rows),
        "correct": scored.correct,
        "accuracy": round(scored.accuracy, 4),
        "yes_without_quote": scored.yes_without_quote,
        "false_yes": scored.false_yes,
        "suggested_right": scored.suggested_right,
        "suggested_wrong": scored.suggested_wrong,
        # Scored as if the provider setting had been the other way round: the same calls.
        "provider_setting_flipped": {
            "provider_on": not provider_on,
            "correct": scored.correct_flipped,
        },
        "unreached": scored.unreached,
        "dropdown_violations": scored.dropdown_violations,
        "integrity": scored.integrity,
        "misses": scored.confusion(),
        "spend": {
            "calls": model.spend.calls,
            "input_tokens": model.spend.input_tokens,
            "cached_tokens": model.spend.cached_tokens,
            "output_tokens": model.spend.output_tokens,
            "dollars": round(
                model.spend.dollars + (checker.spend.dollars if checker else 0.0), 4
            ),
            "errors": model.spend.errors[:20],
            "providers": dict(model.spend.providers),
        },
        "checker_spend": {
            "calls": checker.spend.calls,
            "input_tokens": checker.spend.input_tokens,
            "output_tokens": checker.spend.output_tokens,
            "dollars": round(checker.spend.dollars, 4),
            "errors": checker.spend.errors[:20],
            "providers": dict(checker.spend.providers),
        }
        if checker
        else None,
        "rows": [r.__dict__ for r in scored.rows],
    }
    (folder / "run.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"  {scored.correct}/{len(scored.rows)} correct "
        f"({scored.correct_flipped} with the provider setting {'off' if provider_on else 'on'}), "
        f"false Yes {scored.false_yes}, Yes without quote {scored.yes_without_quote}, "
        f"suggestions right {scored.suggested_right} wrong {scored.suggested_wrong}, "
        f"integrity problems {len(scored.integrity)}, "
        f"${record['spend']['dollars']:.4f}, {record['seconds']}s",
        flush=True,
    )


def _one_or_more(value: str) -> int:
    """--runs 0 would read the pack and cases, run nothing and exit as if it had succeeded."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("give 1 or more")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--pack", type=Path, required=True)
    run_parser.add_argument("--eval", type=Path, required=True)
    run_parser.add_argument("--case", action="append")
    run_parser.add_argument("--model", action="append", required=True)
    run_parser.add_argument(
        "--checker",
        help="the model that makes the second checks; the answering model if left out",
    )
    run_parser.add_argument(
        "--setting",
        action="append",
        help="one of the job's firm settings, as key=true or key=false",
    )
    run_parser.add_argument("--runs", type=_one_or_more, default=1)
    run_parser.add_argument("--concurrency", type=int, default=4)
    run_parser.add_argument("--effort", default="low", help="Claude's effort level")
    run_parser.add_argument(
        "--reasoning",
        choices=("default", "off", "on", "low"),
        default="default",
        help=(
            "an OpenRouter model's thinking: as the app leaves it, forced off or on, or at "
            "low effort for a model that must think"
        ),
    )
    run_parser.add_argument(
        "--embedder",
        choices=("bge", "none"),
        default="bge",
        help="find passages by meaning too, with the app's bundled embedder, or by words alone",
    )
    run_parser.add_argument(
        "--all-rows",
        action="store_true",
        help="answer every question, not only gold ones",
    )
    run_parser.add_argument("--out", type=Path, required=True)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        run(args)
    else:
        sys.stdout.write(report(args.out))


if __name__ == "__main__":
    main()
