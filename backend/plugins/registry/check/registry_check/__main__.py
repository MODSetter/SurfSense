"""`python -m registry_check static|live|sign|verify`: what CI runs over the registry."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from registry_check.live.live_check import live_findings
from registry_check.signing.sign import sign_registry
from registry_check.signing.verify import verify_registry
from registry_check.static.checked_list import problems_in
from registry_check.submission.listing import list_submission
from registry_check.submission.submission_check import check_submission
from registry_check.submission.submission_comment import submission_comment

REGISTRY = Path(__file__).resolve().parents[2] / "plugins.json"
# Written by the sign job only; what the registry container serves.
PUBLISHED = REGISTRY.parent / "published"
FIRST_PARTY = (
    Path(__file__).resolve().parents[5]
    / "surfsense_local/backend/modules/plugins/lists/first_party/plugins.json"
)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.run(args)


def _static(args: argparse.Namespace) -> int:
    return _report(problems_in(args.registry, args.first_party), "static check")


def _live(args: argparse.Namespace) -> int:
    found = live_findings(args.registry, args.base)
    for warning in found.warnings:
        sys.stderr.write(f"{warning}\n")
    return _report(found.problems, "live check")


def _submission(args: argparse.Namespace) -> int:
    logging.getLogger("mcp").setLevel(logging.CRITICAL + 1)
    body = args.issue.read_text(encoding="utf-8")
    found = check_submission(body, args.registry, args.first_party)
    if args.comment:
        args.comment.write_text(submission_comment(found), encoding="utf-8")
    if found.entry is None:
        return _report(found.problems, "submission check")
    if args.apply:
        list_submission(found, args.registry)
        if args.summary:
            summary = {"id": found.entry["id"], "name": found.entry["name"]}
            args.summary.write_text(json.dumps(summary), encoding="utf-8")
    return _report([], "submission check")


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

    live = commands.add_parser(
        "live", help="connect to each new or changed plugin's server"
    )
    live.add_argument(
        "--base",
        type=Path,
        help="the list a pull request is based on; without it, every entry is contacted",
    )
    live.set_defaults(run=_live)

    submission = commands.add_parser(
        "submission", help="check a plugin submission issue, and list it once accepted"
    )
    submission.add_argument("--issue", type=Path, required=True, help="its body")
    submission.add_argument("--comment", type=Path, help="write the issue comment")
    submission.add_argument("--first-party", type=Path, default=FIRST_PARTY)
    submission.add_argument(
        "--apply", action="store_true", help="add the entry and its icon to the list"
    )
    submission.add_argument("--summary", type=Path, help="write its id and name")
    submission.set_defaults(run=_submission)

    sign = commands.add_parser("sign", help="stamp and sign with REGISTRY_SIGNING_KEY")
    sign.add_argument("--published", type=Path, default=PUBLISHED)
    sign.set_defaults(run=_sign)

    verify = commands.add_parser("verify", help="check plugins.json.sig")
    verify.add_argument("--public-key", required=True, help="hex raw Ed25519 key")
    verify.add_argument("--registry", type=Path, default=PUBLISHED / "plugins.json")
    verify.set_defaults(run=_verify)

    for command in (static, live, submission, sign):
        command.add_argument("--registry", type=Path, default=REGISTRY)
    return parser


if __name__ == "__main__":
    sys.exit(main())
