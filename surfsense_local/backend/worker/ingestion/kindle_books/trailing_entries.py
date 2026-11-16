def without_trailing_entries(record: bytes, flags: int) -> bytes:
    """A text record without the entries a writer appends after its text: one per
    flag bit above bit 0, then bit 0's multibyte overlap."""
    for _ in range(bin(flags >> 1).count("1")):
        # Its size, itself included, is written backwards from the end, 7 bits a byte.
        size = 0
        for byte in record[-4:]:
            if byte & 0x80:
                size = 0
            size = (size << 7) | (byte & 0x7F)
        record = record[: len(record) - size]
    if flags & 1 and record:
        record = record[: len(record) - ((record[-1] & 3) + 1)]
    return record
