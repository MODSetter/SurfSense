"""Write the model packs' third-party notices fragment for the desktop installer.

    uv run scripts/write_model_notices.py <fragments-dir>

`build:notices` in electron/ runs it; `scripts/notices/merge.mjs` merges it.
"""

import argparse
import json
from pathlib import Path

from notices.model_packs import model_notices


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fragments", type=Path)
    args = parser.parse_args()
    entries = model_notices()
    args.fragments.mkdir(parents=True, exist_ok=True)
    out = args.fragments / "models.json"
    out.write_text(
        json.dumps({"entries": entries}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(entries)} model packs in {out}")


if __name__ == "__main__":
    main()
