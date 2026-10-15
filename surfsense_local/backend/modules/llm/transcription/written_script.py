"""The language a text's script names, when only one language writes it.

Nemotron tags a sentence only once it ends; a phrase with no closing punctuation
comes back untagged. Latin and Cyrillic serve many languages and say nothing.
"""

import unicodedata
from collections import Counter
from collections.abc import Collection

__all__ = ["language_by_script"]

# The first word of a letter's Unicode name, and the one language it names.
_SCRIPTS = {
    "DEVANAGARI": "hi",
    "HANGUL": "ko",
    "HIRAGANA": "ja",
    "KATAKANA": "ja",
    "CJK": "zh",
    "ARABIC": "ar",
    "THAI": "th",
    "GREEK": "el",
    "HEBREW": "he",
}


def language_by_script(text: str, known: Collection[str]) -> str | None:
    """`known`: the codes the model may answer in; any other is not named."""
    scripts = Counter(
        unicodedata.name(character, "").split(" ", 1)[0]
        for character in text
        if character.isalpha()
    )
    if not scripts:
        return None
    script, _ = scripts.most_common(1)[0]
    language = _SCRIPTS.get(script)
    # Japanese writes Han beside kana; Chinese never uses kana.
    if language == "zh" and (scripts["HIRAGANA"] or scripts["KATAKANA"]):
        language = "ja"
    return language if language in known else None
