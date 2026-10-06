"""Write the capability list the app ships from ladder results.

Run by hand after a ladder run is written up:

    python scripts/write_capability_list.py [results.json]

With no argument it rewrites the list from the committed suite results in
`capability_list/ladder/`. The input's shape is in `capability_list/ladder_input.py`;
the bar each column is held to is in `capability_list/verdict.py`. A person reviews
both diffs and commits them; nothing fetches the list at runtime.
"""

import argparse
import json
from pathlib import Path

from capability_list.ladder_input import LadderResults
from capability_list.rows import COMMITTED_INPUT, measured_rows

from modules.llm.capability.measured.loader import SHIPPED


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", nargs="?", type=Path, default=COMMITTED_INPUT)
    args = parser.parse_args()
    results = LadderResults.model_validate_json(args.results.read_text("utf-8"))
    written = measured_rows(results).model_dump(mode="json")
    SHIPPED.write_text(
        json.dumps(written, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for row in written["models"]:
        passes = row["passes"]
        print(f"{row['key']}: {row['level']} ({passes['passed']}/{passes['counted']})")


if __name__ == "__main__":
    main()
