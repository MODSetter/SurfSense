from modules.documents.kindle_books.container import KindleBookError, u32

IndexEntry = tuple[bytes, dict[int, list[int]]]


def _varlen(data: bytes, at: int) -> tuple[int, int]:
    """A value 7 bits a byte, ended by a byte with its top bit set; and its size."""
    if at >= len(data):
        # Counts come from the file: a damaged one would read zeros forever.
        raise KindleBookError("the book's index is damaged")
    value = size = 0
    for byte in data[at : at + 4]:
        value = (value << 7) | (byte & 0x7F)
        size += 1
        if byte & 0x80:
            break
    return value, size


def index_entries(book_records: list[bytes], first: int) -> list[IndexEntry]:
    """A KF8 INDX table: each entry's name and its values by tag. Its header
    record's TAGX section says which tags an entry may carry and how."""
    head = book_records[first]
    if head[:4] != b"INDX":
        raise KindleBookError("the book's index is missing")
    header_length, entry_records = u32(head, 4), u32(head, 24)
    tagx = head[header_length:]
    if tagx[:4] != b"TAGX":
        raise KindleBookError("the book's index has no tag table")
    control_bytes, tagx_length = u32(tagx, 8), u32(tagx, 4)
    if tagx_length > len(tagx):
        raise KindleBookError("the book's index is damaged")
    tags = [tuple(tagx[at : at + 4]) for at in range(12, tagx_length - 3, 4)]

    entries: list[IndexEntry] = []
    for record in book_records[first + 1 : first + 1 + entry_records]:
        idxt, count = u32(record, 20), u32(record, 24)
        if record[idxt : idxt + 4] != b"IDXT" or idxt + 4 + 2 * count > len(record):
            raise KindleBookError("the book's index is damaged")
        for number in range(count):
            at = int.from_bytes(record[idxt + 4 + 2 * number : idxt + 6 + 2 * number])
            name_end = at + 1 + record[at]
            entries.append(
                (
                    record[at + 1 : name_end],
                    _values(record, name_end, control_bytes, tags),
                )
            )
    return entries


def _values(
    record: bytes, start: int, control_bytes: int, tags: list[tuple[int, ...]]
) -> dict[int, list[int]]:
    position = start + control_bytes
    control = 0
    # Per tag: how many sets of values it has, or how many bytes they fill.
    found: list[tuple[int, int, int | None, int | None]] = []
    for tag, per_entry, mask, end in tags:
        if end & 1:
            control += 1
            continue
        bits = record[start + control] & mask
        if bits == mask and bin(mask).count("1") > 1:
            size, used = _varlen(record, position)
            position += used
            found.append((tag, per_entry, None, size))
        elif bits:
            found.append(
                (tag, per_entry, bits >> ((mask & -mask).bit_length() - 1), None)
            )
    values: dict[int, list[int]] = {}
    for tag, per_entry, sets, size in found:
        got: list[int] = []
        if sets is not None:
            for _ in range(sets * per_entry):
                value, used = _varlen(record, position)
                got.append(value)
                position += used
        else:
            read = 0
            while read < (size or 0):
                value, used = _varlen(record, position)
                got.append(value)
                position += used
                read += used
        values[tag] = got
    return values
