"""How well a tool matches the user's message, so the tools it asks for get the turn's room.

Scored as opencode's own code-mode tool search scores them: a word in the tool's name
counts most, one in its description less. No word in common scores nothing.
"""

import re

from modules.plugins.gateway.ready_tool import ReadyTool

_WORD = re.compile(r"[a-z0-9]+")
# Too common to say which tool is meant.
_IGNORED = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "that",
        "this",
        "what",
        "how",
        "are",
        "can",
        "you",
        "use",
        "please",
        "any",
    ]
)
_IN_NAME = 8
_IN_TEXT = 2


def message_words(text: str) -> frozenset[str]:
    words = set()
    for word in _WORD.findall(text.lower()):
        if len(word) < 3 or word in _IGNORED:
            continue
        words.add(word)
        # "words" finds "word", as "searches" finds "search".
        if word.endswith("es") and len(word) > 4:
            words.add(word[:-2])
        if word.endswith("s") and len(word) > 3:
            words.add(word[:-1])
    return frozenset(words)


def relevance(tool: ReadyTool, words: frozenset[str]) -> int:
    name = tool.tool.lower()
    text = f"{tool.title or ''} {tool.description or ''}".lower()
    return sum(
        (_IN_NAME if word in name else 0) + (_IN_TEXT if word in text else 0)
        for word in words
    )
