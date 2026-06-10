"""Prompt for detecting the dominant natural language of source content."""

from __future__ import annotations

_SYSTEM = """\
You identify the dominant natural language of a piece of source content for a \
podcast that will be generated from it.

Rules:
- Report the language the listener-facing podcast should be spoken in, i.e. the \
language most of the meaningful prose is written in.
- Ignore code, markup, URLs, numbers, and proper nouns when judging.
- If the content is too short, ambiguous, mixed without a clear majority, or not \
natural-language prose, return null rather than guessing.

Respond with strict JSON and nothing else:
{"language": "<BCP-47 tag like en, en-US, fr, pt-BR>"}  or  {"language": null}
"""


def detect_language_prompt() -> str:
    return _SYSTEM
