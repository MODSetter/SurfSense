"""A submission issue checked by the registry's own rules, each problem named by the form's question."""

import json
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio

from registry_check.static.entry_rules import entry_problems
from registry_check.static.icon_rules import icon_problems
from registry_check.static.list_rules import id_problems
from registry_check.submission import issue_form as form
from registry_check.submission.icon_fetch import (
    IconRefusedError,
    fetch_icon,
    icon_address,
    icon_extension,
)
from registry_check.submission.public_address import address_problem
from registry_check.submission.server_report import ServerReport, report_server
from registry_check.submission.submitted_entry import entry_id, submitted_entry

# An entry rule names a field; the submitter only knows the question that fills it.
QUESTION_OF_FIELD = {
    "id": form.NAME,
    "name": form.NAME,
    "url": form.URL,
    "hosts": form.URL,
    "author": form.PUBLISHER,
    "description": form.DESCRIPTION,
    "about": form.ABOUT,
    "privacy_policy": form.PRIVACY_POLICY,
    "homepage": form.HOMEPAGE,
    "access": form.ACCESS,
    "access_note": form.ACCESS_NOTE,
    "auth": form.URL,
    "tools": form.TOOLS,
}

ReportServer = Callable[[str], Awaitable[ServerReport]]
FetchIcon = Callable[[str], Awaitable[bytes]]


@dataclass
class Submission:
    # None while anything is left to fix.
    entry: dict[str, Any] | None
    icon: bytes | None = None
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_submission(
    body: str,
    registry_path: Path,
    first_party_path: Path,
    report_server: ReportServer = report_server,
    fetch_icon: FetchIcon = fetch_icon,
) -> Submission:
    return anyio.run(
        _checked, body, registry_path, first_party_path, report_server, fetch_icon
    )


async def _checked(
    body: str,
    registry_path: Path,
    first_party_path: Path,
    report_server: ReportServer,
    fetch_icon: FetchIcon,
) -> Submission:
    answers = form.answers_in(body)
    problems = [f"{q}: required" for q in form.REQUIRED if not answers.get(q)]
    if not form.all_ticked(answers.get(form.CONFIRMATIONS, "")):
        problems.append(f"{form.CONFIRMATIONS}: tick the box")
    if problems:
        return Submission(None, problems=problems)

    unreachable = address_problem(answers[form.URL])
    if unreachable:
        return Submission(None, problems=[f"{form.URL}: {unreachable}"])
    server = await report_server(answers[form.URL])
    found = Submission(None, warnings=list(server.warnings))
    found.problems += [f"{form.URL}: {p}" for p in server.problems]
    if server.auth.get("user_client"):
        found.warnings.append(
            f"{form.URL}: your sign-in accepts only apps registered with it in advance, "
            "so each user registers their own and signs in with it when connecting"
        )
    tools = _named_tools(answers)
    if not server.problems:
        _compare_tools(found, tools, server)

    icon_name = None
    address = icon_address(answers.get(form.ICON, ""))
    if address:
        try:
            found.icon = await fetch_icon(address)
            icon_name = f"{entry_id(answers[form.NAME])}.{icon_extension(found.icon)}"
        except IconRefusedError as refused:
            found.problems.append(f"{form.ICON}: {refused}")

    entry = submitted_entry(answers, server, tools, icon_name)
    found.problems += _entry_problems(entry, registry_path, first_party_path)
    if found.icon is not None and icon_name:
        found.problems += _icon_problems(entry, icon_name, found.icon)
    if not found.problems:
        found.entry = entry
    return found


def _compare_tools(
    found: Submission, declared: list[str], server: ServerReport
) -> None:
    """The declared list is the record; what the server shows without sign-in checks it."""
    if server.tools is None:
        found.warnings.append(
            f"{form.TOOLS}: your server lists them only after sign-in, so a "
            "maintainer confirms them when connecting it in review"
        )
        return
    left_out = [t for t in server.tools if t not in declared]
    if left_out:
        found.problems.append(
            f"{form.TOOLS}: your server also lists {', '.join(left_out)}; "
            f"add {'it' if len(left_out) == 1 else 'them'}. "
            f"It lists: {', '.join(server.tools)}"
        )
    hidden = [t for t in declared if t not in server.tools]
    if hidden:
        found.warnings.append(
            f"{form.TOOLS}: {', '.join(hidden)} not listed without sign-in; "
            "a maintainer confirms them when connecting"
        )


def _named_tools(answers: dict[str, str]) -> list[str]:
    lines = answers.get(form.TOOLS, "").splitlines()
    return [line.strip(" -*`") for line in lines if line.strip(" -*`")]


def _entry_problems(
    entry: dict[str, Any], registry_path: Path, first_party_path: Path
) -> list[str]:
    problems = [_as_question(p) for p in entry_problems(entry)]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    first_party = json.loads(first_party_path.read_text(encoding="utf-8"))
    plugins = [*registry.get("plugins", []), entry]
    taken = id_problems(
        plugins,
        registry.get("removed", []),
        {e["id"] for e in first_party.get("plugins", [])},
    )
    if any(index == len(plugins) - 1 for index, _ in taken):
        problems.append(
            f"{form.NAME}: another plugin, listed or removed, already has the id "
            f"{entry['id']}; choose another name"
        )
    return problems


def _icon_problems(entry: dict[str, Any], icon_name: str, content: bytes) -> list[str]:
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / icon_name).write_bytes(content)
        found = icon_problems([entry], Path(folder))
    # "plugins[0] "acme": icon: icons/acme.svg is larger…" → the part after the file name.
    return [
        f"{form.ICON}: {p.split(': icon: ', 1)[-1].replace(f'icons/{icon_name} ', '')}"
        for p in found
    ]


def _as_question(problem: str) -> str:
    field_name, _, message = problem.partition(": ")
    return f"{QUESTION_OF_FIELD.get(field_name, field_name)}: {message}"
