"""A list counter written in a w:numFmt, as Word displays it."""

_ROMAN = (
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)

_CHICAGO = ("*", "†", "‡", "§")  # *, dagger, double dagger, section
_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_ORDINAL_WORDS = {
    "one": "first",
    "two": "second",
    "three": "third",
    "five": "fifth",
    "eight": "eighth",
    "nine": "ninth",
    "twelve": "twelfth",
}

# Formats that show no number; every other unknown format reads as decimal.
SILENT_FORMATS = frozenset({"bullet", "none"})

# Formats that repeat a character as the count grows (z, aa; *, **; mmm), and
# the count each repeat adds. A w:start from the file can be in the billions.
_REPEATS_EVERY = {
    "lowerLetter": 26,
    "upperLetter": 26,
    "chicago": 4,
    "lowerRoman": 1000,
    "upperRoman": 1000,
}
# Past this many repeats a number is written in decimal: no list a person
# reads gets there, and the marker stays short.
_MOST_REPEATS = 32


def formatted(value: int, num_fmt: str) -> str:
    if num_fmt in SILENT_FORMATS:
        return ""
    if value <= 0:
        return str(value)
    every = _REPEATS_EVERY.get(num_fmt)
    if every is not None and (value - 1) // every >= _MOST_REPEATS:
        return str(value)
    if num_fmt == "lowerLetter":
        return _letters(value)
    if num_fmt == "upperLetter":
        return _letters(value).upper()
    if num_fmt == "lowerRoman":
        return _roman(value)
    if num_fmt == "upperRoman":
        return _roman(value).upper()
    if num_fmt == "decimalZero":
        return f"{value:02d}"
    if num_fmt == "ordinal":
        return _ordinal(value)
    if num_fmt == "cardinalText":
        return _words(value).capitalize()
    if num_fmt == "ordinalText":
        return _ordinal_words(value).capitalize()
    if num_fmt == "chicago":
        return _CHICAGO[(value - 1) % 4] * ((value - 1) // 4 + 1)
    if num_fmt == "decimalEnclosedCircle" and value <= 20:
        return chr(0x2460 + value - 1)
    return str(value)


def _letters(value: int) -> str:
    # Word repeats the letter past z: y, z, aa, bb.
    return chr(ord("a") + (value - 1) % 26) * ((value - 1) // 26 + 1)


def _roman(value: int) -> str:
    out = []
    for amount, numeral in _ROMAN:
        count, value = divmod(value, amount)
        out.append(numeral * count)
    return "".join(out)


def _ordinal(value: int) -> str:
    suffix = (
        "th"
        if 10 <= value % 100 <= 20
        else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    )
    return f"{value}{suffix}"


def _words(value: int) -> str:
    if value < 20:
        return _ONES[value]
    if value < 100:
        tens, ones = divmod(value, 10)
        return _TENS[tens - 2] + (f"-{_ONES[ones]}" if ones else "")
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        return f"{_ONES[hundreds]} hundred" + (f" {_words(rest)}" if rest else "")
    return str(value)


def _ordinal_words(value: int) -> str:
    cardinal = _words(value)
    head, _, last = cardinal.rpartition("-" if "-" in cardinal else " ")
    joint = cardinal[len(head)] if head else ""
    if last in _ORDINAL_WORDS:
        last = _ORDINAL_WORDS[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    elif not last.isdigit():
        last += "th"
    return f"{head}{joint}{last}"
