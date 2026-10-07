"""`python -m tests.live.sweep run|report`: the 2-case screening sweep over OpenRouter's tool-calling models.

Run from surfsense_local/backend with OPENROUTER_API_KEY in this process's
environment; it reaches only each case's own environment. `run` resumes
whatever its --out folder already holds; `report` prints progress at any time.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from tests.live.live_runs_dir import live_runs_dir
from tests.live.sweep import report
from tests.live.sweep.budget import Budget
from tests.live.sweep.model_list import (
    LISTING_URL,
    fetch_listing,
    measured_keys,
    pick,
    read_listing,
    select,
)
from tests.live.sweep.plan import CASES
from tests.live.sweep.ram_guard import FLOOR_GB, RamGuard
from tests.live.sweep.results import write_atomic
from tests.live.sweep.runner import Runner, Sweep

BACKEND = Path(__file__).resolve().parents[3]
_FILES = {
    "smoke": "test_smoke.py",
    "pdf-brief": "test_pdf_brief.py",
    "board-pack": "test_board_pack.py",
}


def main(argv: list[str] | None = None) -> int:
    """Run or resume the sweep, or report on it."""
    parser = argparse.ArgumentParser(prog="python -m tests.live.sweep")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run or resume the sweep")
    run.add_argument("--out", type=Path, default=live_runs_dir() / "sweep")
    listing = run.add_mutually_exclusive_group()
    listing.add_argument(
        "--listing", type=Path, help="an OpenRouter /models snapshot to choose from"
    )
    listing.add_argument(
        "--fetch", action="store_true", help=f"take a fresh listing from {LISTING_URL}"
    )
    run.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="exactly these ids, measured or not (a pilot)",
    )
    run.add_argument("--lanes", type=int, default=6, help="cases running at once")
    run.add_argument("--budget", type=float, default=200.0, help="dollars, hard cap")
    run.add_argument("--case-dollars", type=float, default=3.0, help="a run's own stop")
    run.add_argument("--case-minutes", type=float, default=20.0)
    run.add_argument("--min-free-gb", type=float, default=2.0)
    run.add_argument("--lane-gb", type=float, default=FLOOR_GB)
    run.add_argument(
        "--retry-unresolved",
        action="store_true",
        help="give cases left unresolved by provider or harness faults their retries back",
    )
    run.add_argument(
        "--dry-run", action="store_true", help="choose the models and stop"
    )
    shown = commands.add_parser("report", help="print the sweep's progress")
    shown.add_argument("--out", type=Path, default=live_runs_dir() / "sweep")
    args = parser.parse_args(argv)

    if args.command == "report":
        print(report.read(args.out.resolve()).text())  # noqa: T201
        return 0
    return _run(args, parser)


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    kept = out / "listing.json"
    if args.fetch:
        write_atomic(kept, fetch_listing())
    elif args.listing is not None and args.listing.resolve() != kept:
        shutil.copyfile(args.listing, kept)
    if not kept.is_file():
        parser.error(f"no listing in {out}: pass --listing <snapshot> or --fetch")
    listing = read_listing(kept)
    selection = select(listing, measured_keys())
    models = pick(listing, args.only) if args.only else selection.sweep
    print(  # noqa: T201
        f"{selection.eligible} models call tools, hold {32_768:,} tokens and are priced; "
        f"{len(selection.measured)} already measured by the 8-case ladder; "
        f"{len(selection.sweep)} to sweep, {len(selection.assumed)} assumed "
        f"(input $3/M and up)"
    )
    if args.only:
        print(f"--only: {len(models)} models")  # noqa: T201
    facts = {
        "file": kept.as_posix(),
        "models_listed": len(listing["data"]),
        "eligible": selection.eligible,
        "measured_left_out": selection.measured,
        "only": bool(args.only),
    }
    write_atomic(
        out / "models.json",
        {
            "listing": facts,
            "sweep": [m.to_json() for m in models],
            "assumed": [m.to_json() for m in selection.assumed],
        },
    )
    if args.dry_run:
        return 0
    if not os.environ.get("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY is not set in this environment")
    sweep = Sweep(
        out=out,
        models=models,
        assumed=selection.assumed,
        listing=facts,
        command_for=pytest_command,
        child_env=dict(os.environ),
        cwd=BACKEND,
        guard=RamGuard(
            lanes=args.lanes, lane_gb=args.lane_gb, min_free_gb=args.min_free_gb
        ),
        budget=Budget(cap=args.budget, case_cap=args.case_dollars),
        case_seconds=args.case_minutes * 60,
        retry_unresolved=args.retry_unresolved,
    )
    Runner(sweep).run()
    print(report.read(out).text())  # noqa: T201
    return 0


def pytest_command(case: str, lane_dir: Path) -> list[str]:
    """One live case in its lane, with the lane's own pytest temp dir."""
    assert case in CASES, case
    return [
        sys.executable,
        "-m",
        "pytest",
        f"tests/live/{_FILES[case]}",
        "-m",
        "live",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(lane_dir / "tmp"),
    ]


if __name__ == "__main__":
    sys.exit(main())
