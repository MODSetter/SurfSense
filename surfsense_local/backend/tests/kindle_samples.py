"""Kindle books built byte by byte, as calibre and kindlegen lay them out, so no
third-party book has to sit in the repository."""

import struct

TEXT_RECORD_SIZE = 4096
_HEADER_LENGTH = 264  # Reaches the KF8 skeleton field at 252.


def container(records: list[bytes], kind: bytes = b"BOOKMOBI") -> bytes:
    """A Palm database: a 78-byte header, the record table, then the records."""
    head = bytearray(78)
    head[:8] = b"sample\0\0"
    head[60:68] = kind
    struct.pack_into(">H", head, 76, len(records))
    offset = 78 + 8 * len(records) + 2
    table = bytearray()
    for index, record in enumerate(records):
        table += struct.pack(">II", offset, index)
        offset += len(record)
    return bytes(head + table + b"\0\0" + b"".join(records))


def mobi_header(
    *,
    text_length: int,
    text_records: int,
    compression: int = 1,
    encryption: int = 0,
    version: int = 6,
    trailing_flags: int = 0,
    huff: tuple[int, int] = (0, 0),
    kf8_indexes: tuple[int, int] | None = None,
    exth: dict[int, bytes] | None = None,
) -> bytes:
    """Record 0: the PalmDOC header, the MOBI header and any EXTH records."""
    palmdoc = struct.pack(
        ">HHIHHHH",
        compression,
        0,
        text_length,
        text_records,
        TEXT_RECORD_SIZE,
        encryption,
        0,
    )
    mobi = bytearray(_HEADER_LENGTH)
    mobi[:4] = b"MOBI"
    struct.pack_into(">III", mobi, 4, _HEADER_LENGTH, 2, 65001)
    struct.pack_into(">I", mobi, 20, version)
    struct.pack_into(">II", mobi, 96, *huff)
    struct.pack_into(">I", mobi, 224, trailing_flags)
    frag, skel = kf8_indexes or (0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into(">II", mobi, 232, frag, skel)
    tail = b""
    if exth:
        struct.pack_into(">I", mobi, 112, 0x40)
        entries = b"".join(
            struct.pack(">II", kind, 8 + len(value)) + value
            for kind, value in exth.items()
        )
        tail = b"EXTH" + struct.pack(">II", 12 + len(entries), len(exth)) + entries
    return palmdoc + bytes(mobi) + tail


def text_records(text: bytes) -> list[bytes]:
    """The text cut into 4 KB records, as every writer stores it."""
    return [
        text[at : at + TEXT_RECORD_SIZE] for at in range(0, len(text), TEXT_RECORD_SIZE)
    ] or [b""]


def palmdoc(chunk: bytes) -> bytes:
    """PalmDOC's LZ77, greedily: every code kind the format has, overlaps included."""
    out = bytearray()
    at = 0
    while at < len(chunk):
        best_length = best_distance = 0
        for distance in range(1, min(at, 2047) + 1):
            length = 0
            while (
                length < 10
                and at + length < len(chunk)
                and chunk[at + length - distance] == chunk[at + length]
            ):
                length += 1
            if length > best_length:
                best_length, best_distance = length, distance
        byte = chunk[at]
        if best_length >= 3:
            out += struct.pack(">H", 0x8000 | (best_distance << 3) | (best_length - 3))
            at += best_length
        elif byte == 0x20 and at + 1 < len(chunk) and 0x40 <= chunk[at + 1] < 0x80:
            out.append(chunk[at + 1] ^ 0x80)
            at += 2
        elif byte == 0 or 0x09 <= byte < 0x80:
            out.append(byte)
            at += 1
        else:
            out += bytes([1, byte])
            at += 1
    return bytes(out)


# After each record's text: a multibyte entry ("Z" and its size byte), then one
# trailing entry of four bytes, its size written backwards at its end.
TRAILING = b"Z\x01" + b"junk" + bytes([0x80 | 5])
TRAILING_FLAGS = 0b11


def mobi(
    html: str, *, encryption: int = 0, compression: int = 1, trailing: bool = False
) -> bytes:
    """A MOBI 6 book, uncompressed as kindlegen -c0 writes it or PalmDOC as calibre does."""
    text = html.encode()
    records = text_records(text)
    huff_records: list[bytes] = []
    if compression == 2:
        records = [palmdoc(record) for record in records]
    elif compression == 17480:
        records = [huffcdic(record) for record in records]
        huff_records = huffcdic_tables()
    if trailing:
        records = [record + TRAILING for record in records]
    header = mobi_header(
        text_length=len(text),
        text_records=len(records),
        compression=compression,
        encryption=encryption,
        trailing_flags=TRAILING_FLAGS if trailing else 0,
        huff=(1 + len(records), len(huff_records)) if huff_records else (0, 0),
    )
    return container([header, *records, *huff_records])


# Dictionary entry 0 is itself compressed, as kindlegen nests common phrases.
NESTED = b"Ishmael"


def huffcdic(chunk: bytes) -> bytes:
    """Every code 8 bits long: code byte 255 - i stands for dictionary entry i,
    entry i being byte i, but for entry 0, which is NESTED."""
    return bytes(255 - byte for byte in chunk.replace(NESTED, b"\0"))


def huffcdic_tables(entries: list[tuple[bytes, bool]] | None = None) -> list[bytes]:
    """The HUFF record, every code 8 bits, and one CDIC record of the entries."""
    found_at_8_bits = 0x80 | 8 | (255 << 8)
    table1 = b"".join(struct.pack(">I", found_at_8_bits) for _ in range(256))
    huff = b"HUFF" + struct.pack(">III", 24, 24, 24 + len(table1)) + bytes(8)
    huff += table1 + bytes(32 * 8)

    if entries is None:
        nested = bytes(255 - byte for byte in NESTED)
        entries = [(nested, False)] + [(bytes([i]), True) for i in range(1, 256)]
    body_offsets, body = bytearray(), bytearray()
    for data, unpacked in entries:
        body_offsets += struct.pack(">H", 2 * len(entries) + len(body))
        body += struct.pack(">H", len(data) | (0x8000 if unpacked else 0)) + data
    cdic = b"CDIC" + struct.pack(">III", 16, len(entries), 8) + body_offsets + body
    return [huff, cdic]


def _varlen(value: int) -> bytes:
    """Seven bits a byte, most significant first; the last byte has its top bit set."""
    out = [value & 0x7F | 0x80]
    value >>= 7
    while value:
        out.insert(0, value & 0x7F)
        value >>= 7
    return bytes(out)


_INDX_HEADER_LENGTH = 192


def index(
    entries: list[tuple[bytes, dict[int, list[int]]]],
    tags: list[tuple[int, int, int]],
) -> list[bytes]:
    """An INDX table as two records: the header with its TAGX tag table, then one
    record of entries. Each tag is (tag, values per entry, control-byte mask)."""
    tagx = b"".join(bytes([tag, per_entry, mask, 0]) for tag, per_entry, mask in tags)
    tagx += bytes([0, 0, 0, 1])
    tagx = b"TAGX" + struct.pack(">II", 12 + len(tagx), 1) + tagx
    head = bytearray(_INDX_HEADER_LENGTH)
    head[:4] = b"INDX"
    struct.pack_into(">I", head, 4, _INDX_HEADER_LENGTH)
    struct.pack_into(">I", head, 24, 1)

    body, offsets = bytearray(), []
    for name, values in entries:
        offsets.append(_INDX_HEADER_LENGTH + len(body))
        control = 0
        for tag, _, mask in tags:
            if tag in values:
                control |= mask & -mask  # One set of values for each tag.
        body += bytes([len(name)]) + name + bytes([control])
        for tag, _, _ in tags:
            for value in values.get(tag, []):
                body += _varlen(value)
    idxt_at = _INDX_HEADER_LENGTH + len(body)
    idxt = b"IDXT" + b"".join(struct.pack(">H", at) for at in offsets)
    record = bytearray(_INDX_HEADER_LENGTH)
    record[:4] = b"INDX"
    struct.pack_into(">I", record, 4, _INDX_HEADER_LENGTH)
    struct.pack_into(">II", record, 20, idxt_at, len(entries))
    return [bytes(head) + tagx, bytes(record) + body + idxt]


SKELETON_TAGS = [(1, 1, 0x03), (6, 2, 0x0C)]
# calibre's fragment tags: selector, file, sequence, then offset and length.
FRAGMENT_TAGS = [(2, 1, 0x01), (3, 1, 0x02), (4, 1, 0x04), (6, 2, 0x08)]


def kf8_part(
    chapters: list[list[str]], encryption: int = 0, fragment_repeats: int = 1
) -> list[bytes]:
    """A KF8 book's records: record 0, the text, the skeleton and fragment indexes.
    Each chapter is one XHTML file whose body is filled by its fragments in order.
    A crafted book lists each fragment more than once."""
    raw = bytearray()
    skeletons: list[tuple[bytes, dict[int, list[int]]]] = []
    fragments: list[tuple[bytes, dict[int, list[int]]]] = []
    for number, chapter in enumerate(chapters):
        skeleton = (
            f'<html><head><title>{number}</title></head><body aid="{number}">'
            "</body></html>"
        ).encode()
        start = len(raw)
        insert_at = start + skeleton.index(b"</body>")
        raw += skeleton
        after_skeleton = 0
        for sequence, fragment in enumerate(chapter):
            piece = fragment.encode()
            fragments += [
                (
                    str(insert_at).encode(),
                    {
                        2: [0],
                        3: [number],
                        4: [sequence],
                        6: [after_skeleton, len(piece)],
                    },
                )
            ] * fragment_repeats
            raw += piece
            # The next one goes after this one, in the file as it is put together.
            insert_at += len(piece)
            after_skeleton += len(piece)
        skeletons.append(
            (
                f"SKEL{number:010d}".encode(),
                {1: [len(chapter) * fragment_repeats], 6: [start, len(skeleton)]},
            )
        )
    texts = text_records(bytes(raw))
    skel_at = 1 + len(texts)
    header = mobi_header(
        text_length=len(raw),
        text_records=len(texts),
        encryption=encryption,
        version=8,
        kf8_indexes=(skel_at + 2, skel_at),
    )
    return [
        header,
        *texts,
        *index(skeletons, SKELETON_TAGS),
        *index(fragments, FRAGMENT_TAGS),
    ]


def azw3(chapters: list[list[str]], fragment_repeats: int = 1) -> bytes:
    """A KF8-only book, as calibre writes an AZW3."""
    return container(kf8_part(chapters, fragment_repeats=fragment_repeats))


def combined(
    html: str,
    chapters: list[list[str]],
    *,
    damaged_kf8: bool = False,
    kf8_encryption: int = 0,
) -> bytes:
    """A MOBI 6 copy and a KF8 copy of a book in one file, as kindlegen writes one;
    EXTH 121 names the record the KF8 part starts at."""
    text = html.encode()
    texts = text_records(text)
    boundary = 1 + len(texts) + 1
    header = mobi_header(
        text_length=len(text),
        text_records=len(texts),
        exth={121: struct.pack(">I", boundary)},
    )
    kf8 = kf8_part(chapters, encryption=kf8_encryption)
    if damaged_kf8:
        # The skeleton index's header no longer says INDX.
        kf8[-4] = b"XXXX" + kf8[-4][4:]
    return container([header, *texts, b"BOUNDARY", *kf8])


def huffcdic_book(codes: bytes, entries: list[tuple[bytes, bool]]) -> bytes:
    """A HUFF/CDIC book whose one text record is these codes, over this dictionary;
    code byte 255 - i stands for entry i, which is compressed unless marked unpacked."""
    tables = huffcdic_tables(entries)
    header = mobi_header(
        text_length=len(codes),
        text_records=1,
        compression=17480,
        huff=(2, len(tables)),
    )
    return container([header, codes, *tables])


def palmdoc_text(text: str, *, encryption: int = 0) -> bytes:
    """A plain PalmDOC e-text: record 0 is the PalmDOC header alone."""
    data = text.encode("cp1252")
    records = [palmdoc(record) for record in text_records(data)]
    header = struct.pack(
        ">HHIHHHH", 2, 0, len(data), len(records), TEXT_RECORD_SIZE, encryption, 0
    )
    return container([header, *records], kind=b"TEXtREAd")
