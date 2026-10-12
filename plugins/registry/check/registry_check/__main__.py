"""`python -m registry_check static|sign|verify`: what CI runs over the registry."""

import argparse
import os
import sys
from pathlib import Path

from registry_check.signing.sign import sign_registry
from registry_check.signing.verify import verify_registry
from registry_check.static.checked_list import problems_in

REGISTRY = Path(__file__).resolve().parents[2] / "plugins.json"
# Written by the sign job only; what the registry container serves.
PUBLISHED = REGISTRY.parent / "published"
FIRST_PARTY = (
    Path(__file__).resolve().parents[4]
    / "surfsense_local/backend/modules/plugins/lists/first_party/plugins.json"
)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.run(args)


def _static(args: argparse.Namespace) -> int:
    return _report(problems_in(args.registry, args.first_party), "static check")


def _sign(args: argparse.Namespace) -> int:
    key = os.environ.get("REGISTRY_SIGNING_KEY")
    if not key:
        sys.stderr.write("REGISTRY_SIGNING_KEY is not set\n")
        return 1
    try:
        sign_registry(args.registry, args.published, key)
    except ValueError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(f"signed {args.registry} into {args.published}\n")
    return 0


def _verify(args: argparse.Namespace) -> int:
    if verify_registry(args.registry, args.public_key):
        sys.stdout.write(f"{args.registry} verifies\n")
        return 0
    sys.stderr.write(f"{args.registry} does not verify with {args.public_key}\n")
    return 1


def _report(problems: list[str], name: str) -> int:
    for problem in problems:
        sys.stderr.write(f"{problem}\n")
    if problems:
        sys.stderr.write(f"{name}: {len(problems)} problem(s)\n")
        return 1
    sys.stderr.write(f"{name}: passed\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="registry_check")
    commands = parser.add_subparsers(required=True)

    static = commands.add_parser("static", help="check the entry rules and icons")
    static.add_argument("--first-party", type=Path, default=FIRST_PARTY)
    static.set_defaults(run=_static)

    sign = commands.add_parser("sign", help="stamp and sign with REGISTRY_SIGNING_KEY")
    sign.add_argument("--published", type=Path, default=PUBLISHED)
    sign.set_defaults(run=_sign)

    verify = commands.add_parser("verify", help="check plugins.json.sig")
    verify.add_argument("--public-key", required=True, help="hex raw Ed25519 key")
    verify.add_argument("--registry", type=Path, default=PUBLISHED / "plugins.json")
    verify.set_defaults(run=_verify)

    for command in (static, sign):
        command.add_argument("--registry", type=Path, default=REGISTRY)
    return parser


if __name__ == "__main__":
    sys.exit(main())
