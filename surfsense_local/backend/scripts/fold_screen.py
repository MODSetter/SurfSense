"""Fold a re-run into the committed OpenRouter screen, at the JSON level.

Run by hand once a re-run is written up, from `surfsense_local/backend`:

    python scripts/fold_screen.py path/to/sweep-results.json

Rewrites `capability_list/sweep/openrouter-screen-v1.json` in place with
the re-run folded in (see `capability_list/screen.py`), keeping the
provenance extras the committed screen carries. Review the diff, then
run `catalog_rows.py` on the folded screen — never on the bare re-run.
"""

import argparse
import json
from pathlib import Path

from capability_list.screen import folded_screen, read_screen, write_screen


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path)
    args = parser.parse_args(argv)
    rerun = json.loads(args.results.read_text(encoding="utf-8"))
    screen = folded_screen(read_screen(), rerun)
    write_screen(screen)
    print(
        f"folded: {len(screen['models'])} models, "
        f"{len(screen['unfinished'])} unfinished, {len(screen['assumed'])} assumed"
    )


if __name__ == "__main__":
    main()
