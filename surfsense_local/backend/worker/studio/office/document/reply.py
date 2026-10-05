"""What a model's reply holds: the whole Markdown or the whole script, and its title."""

import re

# As long as the fence the refine request used: a spec with a chart goes out in
# four backticks, and the model answers in kind.
_WHOLE_FENCE = re.compile(
    r"\A\s*(`{3,})(?:markdown|md)?[ \t]*\n(.*)\n\1\s*\Z", re.DOTALL
)
# A fence the model labelled Markdown, with a note before or after it.
_LABELLED_FENCE = re.compile(
    r"^(`{3,})(?:markdown|md)[ \t]*\n(.*)\n\1[ \t]*$", re.DOTALL | re.MULTILINE
)
_CODE_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)
_SCRIPT_TITLE = re.compile(r"^#\s*title:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_HEADING = re.compile(r"^# +(.+?)\s*#*\s*$", re.MULTILINE)
TITLE_CHARS = 200


def markdown_reply(raw: str) -> str:
    """The document, unwrapped when the model fenced all of it."""
    fenced = _WHOLE_FENCE.match(raw) or _LABELLED_FENCE.search(raw)
    return (fenced.group(2) if fenced else raw).strip()


def script_reply(raw: str) -> str:
    """The script, unwrapped from a ```python fence when there is one."""
    fenced = _CODE_FENCE.search(raw)
    return (fenced.group(1) if fenced else raw).strip()


def first_heading(markdown: str) -> str | None:
    found = _HEADING.search(markdown)
    return found.group(1)[:TITLE_CHARS] if found else None


def script_title(script: str) -> str | None:
    """The `# title:` comment the prompt asks a script to open with."""
    found = _SCRIPT_TITLE.search(script)
    return found.group(1)[:TITLE_CHARS] if found else None
