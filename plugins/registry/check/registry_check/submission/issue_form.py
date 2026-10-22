"""The answers in a plugin submission issue, read the way GitHub renders an issue form.

Each question is a `### <label>` heading over its answer; a blank one reads `_No response_`.
The labels are `.github/ISSUE_TEMPLATE/plugin-submit.yml`'s; change them together.
"""

import re

NAME = "Plugin name"
URL = "MCP server URL"
PUBLISHER = "Publisher"
DESCRIPTION = "One-line description"
ABOUT = "About"
PRIVACY_POLICY = "Privacy policy URL"
HOMEPAGE = "Homepage"
ICON = "Icon"
ACCESS = "Who can use it"
ACCESS_NOTE = "What users must buy or have"
TOOLS = "Tool names"
PROMPT = "A prompt to try"
CONFIRMATIONS = "Before you send"

REQUIRED = (
    NAME,
    URL,
    PUBLISHER,
    DESCRIPTION,
    ABOUT,
    PRIVACY_POLICY,
    ACCESS,
    TOOLS,
    PROMPT,
)
FREE = "Free (a free account is fine)"
PAID = "Paid: users need a plan or subscription you sell"

_HEADING = re.compile(r"^### (.+?)\s*$", re.MULTILINE)
_BLANK = "_No response_"
_TICKED = re.compile(r"^- \[[xX]\] ", re.MULTILINE)
_ITEM = re.compile(r"^- \[[ xX]\] ", re.MULTILINE)


def answers_in(body: str) -> dict[str, str]:
    """Each question's answer, stripped; a blank answer is an empty string."""
    text = body.replace("\r\n", "\n")
    headings = list(_HEADING.finditer(text))
    answers = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        answer = text[heading.end() : end].strip()
        answers[heading.group(1)] = "" if answer == _BLANK else answer
    return answers


def all_ticked(answer: str) -> bool:
    """Every box under a checkboxes question is ticked, and there is at least one."""
    items = _ITEM.findall(answer)
    return bool(items) and len(_TICKED.findall(answer)) == len(items)
