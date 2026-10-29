from modules.documents.kindle_books.container import (
    MAX_UNPACKED_RECORD,
    KindleBookError,
)


def palmdoc_decompress(data: bytes) -> bytes:
    """PalmDOC's LZ77, as calibre and most MOBI writers compress a text record."""
    out = bytearray()
    at, end = 0, len(data)
    while at < end:
        code = data[at]
        at += 1
        if 1 <= code <= 8:
            out += data[at : at + code]
            at += code
        elif code < 0x80:
            out.append(code)
        elif code >= 0xC0:
            out += b" "
            out.append(code ^ 0x80)
        elif at < end:
            pair = (code << 8) | data[at]
            at += 1
            distance, length = (pair & 0x3FFF) >> 3, (pair & 7) + 3
            if not 0 < distance <= len(out):
                raise KindleBookError("the book's text is damaged")
            start = len(out) - distance
            if distance >= length:
                out += out[start : start + length]
            else:
                # An overlapping copy repeats what it has just written.
                for offset in range(length):
                    out.append(out[start + offset])
        if len(out) > MAX_UNPACKED_RECORD:
            raise KindleBookError("the book's text is damaged")
    return bytes(out)
