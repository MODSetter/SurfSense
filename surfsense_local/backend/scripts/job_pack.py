"""A job pack author's two commands: list every file with its sha256, and zip the sealed pack.

    python scripts/job_pack.py seal <pack dir>
    python scripts/job_pack.py zip <pack dir> <out .zip>

The app installs a pack from either the folder or the zip, and refuses one whose files
differ from what `seal` wrote.
"""

import argparse
from pathlib import Path

from modules.jobs.packs.seal import seal_pack, zip_pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("pack", type=Path)
    zipped = commands.add_parser("zip")
    zipped.add_argument("pack", type=Path)
    zipped.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.command == "seal":
        manifest = seal_pack(args.pack)
        print(
            f"{manifest['id']} {manifest['version']}: {len(manifest['files'])} files sealed"
        )
    else:
        print(zip_pack(args.pack, args.out))


if __name__ == "__main__":
    main()
