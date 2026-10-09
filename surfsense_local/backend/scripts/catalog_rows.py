"""Add the OpenRouter screening sweep's rows to the capability list the app ships.

Run by hand once a sweep is written up, from `surfsense_local/backend`:

    python scripts/catalog_rows.py path/to/sweep-results.json [--date 2026-10-07]

Each screened model becomes an `openrouter-screen` row, at `agent` when it
passed both cases and `studio_only` otherwise; each assumed flagship an
`assumed` row. A model the list already names keeps its row unless the new
one outranks it (a screening over an assumption), and a model the sweep has
no verdict for gets none, nor does a variant of it such as its -chat model. The input's shape is in
`capability_list/sweep_input.py`. A person reviews the diff and commits
it; nothing fetches the list at runtime.
"""

import argparse
from datetime import date
from pathlib import Path

from capability_list.merge import merged
from capability_list.shipped import read_shipped, write_shipped
from capability_list.sweep_input import SweepResults
from capability_list.sweep_rows import sweep_rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        help="the day the sweep ran, when its results do not say",
    )
    args = parser.parse_args(argv)
    sweep = SweepResults.model_validate_json(args.results.read_text("utf-8"))
    rows = sweep_rows(sweep, args.date)
    written, left_out = merged(read_shipped(), rows)
    write_shipped(written)
    for row in rows:
        if all(row is not out.row for out in left_out):
            print(f"{row.key}: {row.level} ({row.passes.passed}/{row.passes.counted})")
    for out in left_out:
        whose = "the list's" if out.listed else "this sweep's"
        if out.replaced:
            print(
                f"{out.row.key} ({out.row.suite}): replaced by {whose} "
                f"{out.kept.key} ({out.kept.suite})"
            )
            continue
        print(
            f"{out.row.key} ({out.row.suite}): left out, {whose} "
            f"{out.kept.key} ({out.kept.suite}) names the same model"
        )
    for model in sweep.models:
        if model.finished and (base := sweep.waiting_for(model)) is not None:
            print(f"{model.key}: left out, waiting for {base.key}")
    for model in sweep.left_out():
        print(f"{model.key}: left out, {model.status or 'no verdict'}")


if __name__ == "__main__":
    main()
