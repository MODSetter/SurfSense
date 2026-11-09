"""The registry entry a submission makes: the publisher's answers plus what the server said."""

import datetime
import re
from typing import Any

from registry_check.submission import issue_form as form
from registry_check.submission.server_report import ServerReport


def entry_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def submitted_entry(
    answers: dict[str, str],
    server: ServerReport,
    tools: list[str],
    icon_name: str | None,
) -> dict[str, Any]:
    """In the order the registry's own entries keep; optional fields only when given."""
    # A key's wording is left to the app's own, translated; the key itself is the user's.
    auth = dict(server.auth)
    paid = answers.get(form.ACCESS) == form.PAID
    entry: dict[str, Any] = {
        "id": entry_id(answers[form.NAME]),
        "kind": "remote",
        # Only a maintainer sets `verified`, in review.
        "verification": "community",
        "name": answers[form.NAME],
        "description": answers[form.DESCRIPTION],
        "author": answers[form.PUBLISHER],
        "url": answers[form.URL],
        "auth": auth,
        "hosts": server.hosts,
        "access": "external" if paid else "free",
    }
    if paid:
        entry["access_note"] = answers.get(form.ACCESS_NOTE, "")
    entry["privacy_policy"] = answers[form.PRIVACY_POLICY]
    if answers.get(form.HOMEPAGE):
        entry["homepage"] = answers[form.HOMEPAGE]
    if icon_name:
        entry["icon"] = icon_name
    entry["tools"] = tools
    entry["added"] = datetime.datetime.now(datetime.UTC).strftime("%Y-%m")
    entry["about"] = answers[form.ABOUT]
    return entry
