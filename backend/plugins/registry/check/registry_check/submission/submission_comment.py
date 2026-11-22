"""The one comment the intake workflow keeps up to date on a submission issue."""

import json

from registry_check.submission.submission_check import Submission

ACCEPT_LABEL = "registry: accept"
# Finds the comment again, so each edit of the issue updates it rather than adding one.
MARKER = "<!-- registry-submission -->"


def submission_comment(found: Submission) -> str:
    if found.entry is None:
        lines = [
            MARKER,
            "### A few things to fix",
            "",
            *(f"- {_bold_question(p)}" for p in found.problems),
            *_notes(found.warnings),
            "",
            "Edit this issue to fix them. The checks run again on every edit.",
        ]
        return "\n".join(lines) + "\n"
    lines = [
        MARKER,
        "### Checks passed",
        "",
        "A maintainer connects your plugin and reviews its tools, then adds the "
        f"`{ACCEPT_LABEL}` label. A pull request listing it follows on its own, and "
        "your plugin reaches the app with SurfSense's next release.",
    ]
    lines += _notes(found.warnings)
    lines += [
        "",
        "<details><summary>The entry this makes</summary>",
        "",
        "```json",
        json.dumps(found.entry, indent=2, ensure_ascii=False),
        "```",
        "",
        "</details>",
    ]
    return "\n".join(lines) + "\n"


def _notes(warnings: list[str]) -> list[str]:
    if not warnings:
        return []
    heading = "Worth a look, though nothing here stops the listing:"
    return ["", heading, "", *(f"- {_inert(w)}" for w in warnings)]


def _bold_question(problem: str) -> str:
    question, _, message = problem.partition(": ")
    return f"**{_inert(question)}:** {_inert(message)}"


def _inert(text: str) -> str:
    """Submitted text, echoed in a problem, can neither mention anyone nor add markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace("@", "&#64;")
