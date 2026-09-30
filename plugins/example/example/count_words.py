"""The count-words action: a text's most frequent words, kept as a note."""

import re
from collections import Counter

from surfsense_plugin_sdk import action, document
from tabulate import tabulate

from example.notes_added import next_note_number

# How many words the table lists when the user leaves it empty.
TOP_WORDS = 10


@action("count-words")
def count_words(text: str, top: float | None) -> None:
    """Adds a note with the text and a table of its most frequent words."""
    words = Counter(re.findall(r"\w+", text.lower()))
    table = tabulate(
        words.most_common(int(top or TOP_WORDS)),
        headers=["Word", "Count"],
        tablefmt="github",
    )
    document.add(
        title=f"Word count #{next_note_number()}", content=f"{text}\n\n{table}\n"
    )
