from collections.abc import Callable

from modules.documents.kindle_books.container import (
    MAX_UNPACKED_RECORD,
    KindleBookError,
    u16,
    u32,
)

# A dictionary entry may be compressed with the same codes; real books nest a
# few levels, so deeper than this is a loop in a damaged file.
_MAX_NESTING = 32


def huffcdic_decompressor(tables: list[bytes]) -> Callable[[bytes], bytes]:
    """kindlegen's Huffman coding: the HUFF record's code tables, then the
    CDIC records' dictionary of byte strings the codes stand for."""
    if not tables or tables[0][:4] != b"HUFF":
        raise KindleBookError("the book's HUFF record is missing")
    huff = tables[0]
    by_first_byte_at, by_length_at = u32(huff, 8), u32(huff, 12)
    by_first_byte = [u32(huff, by_first_byte_at + 4 * i) for i in range(256)]
    # Per code length 1-32: the smallest code of that length, and the largest.
    smallest = [0] + [u32(huff, by_length_at + 8 * i) for i in range(32)]
    largest = [0] + [u32(huff, by_length_at + 8 * i + 4) for i in range(32)]

    dictionary: list[tuple[bytes, bool]] = []
    for cdic in tables[1:]:
        if cdic[:4] != b"CDIC":
            raise KindleBookError("the book's CDIC record is missing")
        header_length, total, code_bits = u32(cdic, 4), u32(cdic, 8), u32(cdic, 12)
        body = cdic[header_length:]
        for index in range(min(1 << code_bits, total - len(dictionary))):
            at = u16(body, 2 * index)
            word = u16(body, at)
            dictionary.append(
                (body[at + 2 : at + 2 + (word & 0x7FFF)], bool(word & 0x8000))
            )

    def decompress(data: bytes, depth: int = 0) -> bytes:
        if depth > _MAX_NESTING:
            raise KindleBookError("the book's text is damaged")
        out = bytearray()
        bit_count = len(data) * 8
        # Padded so a 32-bit window can always be read past the last code.
        bits = int.from_bytes(data + bytes(4), "big")
        width = bit_count + 32
        position = 0
        while position < bit_count:
            window = (bits >> (width - position - 32)) & 0xFFFFFFFF
            entry = by_first_byte[window >> 24]
            length, top = entry & 0x1F, entry >> 8
            if not entry & 0x80:
                while length < 32 and window >> (32 - length) < smallest[length]:
                    length += 1
                top = largest[length]
            if length == 0 or position + length > bit_count:
                break
            position += length
            index = top - (window >> (32 - length))
            if not 0 <= index < len(dictionary):
                raise KindleBookError("the book's text is damaged")
            text, unpacked = dictionary[index]
            if not unpacked:
                text = decompress(text, depth + 1)
                dictionary[index] = (text, True)
            out += text
            if len(out) > MAX_UNPACKED_RECORD:
                raise KindleBookError("the book's text is damaged")
        return bytes(out)

    return decompress
