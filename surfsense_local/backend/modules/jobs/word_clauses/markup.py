"""Formatting in a change's new words that the contract does not use: what a model writes when its
reply runs on past the end of a string, such as a tag, a Markdown link or JSON's closing brace.

A mark counts only when no paragraph of the contract writes one of its kind, so new words may use
any mark the contract itself uses.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

_KINDS = (
    ("a tag", re.compile(r"</?[A-Za-z][\w.:-]*(?:\s[^<>]*)?/?>")),
    ("a Markdown link", re.compile(r"\]\(")),
    ("an elision", re.compile(r"\.\.\.|" + chr(0x2026))),
    ("a brace", re.compile(r"[{}]")),
    ("a backtick", re.compile(r"`")),
)
_BRACKETS = (("(", ")"), ("[", "]"))


@dataclass(frozen=True)
class Markup:
    kind: str  # what the model is told it wrote
    word: str  # the run of the new text, between spaces, that holds it


def stray_markup(new: str, replaced: str, contract: Sequence[str]) -> Markup | None:
    """The first mark in `new`, the words that take the place of `replaced` ("" for a new
    paragraph), of a kind the contract's paragraphs never write; None when there is none."""
    whole = "\n".join(contract)
    for kind, pattern in _KINDS:
        found = pattern.search(new)
        if found and not pattern.search(whole):
            return Markup(kind, _word(new, found.start(), found.end()))
    for opening, closing in _BRACKETS:
        lone = _lone(new, opening, closing)
        if len(lone) > len(_lone(replaced, opening, closing)) and not any(
            _lone(text, opening, closing) for text in contract
        ):
            # The last one: a reply that runs on leaves its marks at the end.
            at = lone[-1]
            return Markup(
                "a closing bracket that closes nothing", _word(new, at, at + 1)
            )
    return None


def _lone(text: str, opening: str, closing: str) -> list[int]:
    """Where `text` closes a bracket it never opened."""
    depth, lone = 0, []
    for at, character in enumerate(text):
        if character == opening:
            depth += 1
        elif character == closing:
            if depth:
                depth -= 1
            else:
                lone.append(at)
    return lone


def _word(text: str, start: int, end: int) -> str:
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < len(text) and not text[end].isspace():
        end += 1
    return text[start:end]
