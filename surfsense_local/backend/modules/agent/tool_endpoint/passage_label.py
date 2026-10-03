"""A search passage's label: written into the search's output, read back to know what the agent was given."""

import re

_OPENING = re.compile(r'<passage cite="\[(\d+)\]"')
# Any passage tag a source's own text carries, which could otherwise forge a label.
_PASSAGE_TAGS = re.compile(r"</?passage\b[^>]*>", re.IGNORECASE)


def opening(chunk_id: int) -> str:
    """How a passage starts: with the label the agent is told to cite."""
    return f'<passage cite="[{chunk_id}]"'


def without_passage_tags(text: str) -> str:
    """A source's text, with no tag in it that could pass for a passage."""
    return _PASSAGE_TAGS.sub("", text)


def labelled_chunks(search_output: str) -> list[int]:
    """The chunks a search's output labelled, in the order given."""
    return [int(chunk_id) for chunk_id in _OPENING.findall(search_output)]
