"""How many notes the word counter has added, kept in its own data folder."""

from surfsense_plugin_sdk import data


def next_note_number() -> int:
    """One more than last time; the folder survives updates, so the count does too."""
    counter = data() / "notes-added.txt"
    number = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(number))
    return number
