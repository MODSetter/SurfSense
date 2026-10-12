"""Encode Apify search filters into YouTube's ``sp=`` (InnerTube ``params``).

YouTube encodes search filters as a base64 protobuf. The message is::

    SearchParams {
        1: sortOrder   (varint enum)
        2: Filters {
            1: uploadDate (varint enum)
            2: type       (varint enum)
            3: duration   (varint enum)
            <feature fields>: bool (varint 1)
        }
    }

Rather than a lookup table of single tokens, we build the protobuf directly so
arbitrary combinations (sort + date + type + length + any boolean features)
compose correctly. The field numbers/enums below are verified to reproduce
YouTube's own standalone tokens byte-for-byte (see the unit test).
"""

from __future__ import annotations

import base64

_SORT_ORDER = {"relevance": 0, "rating": 1, "date": 2, "views": 3}
_UPLOAD_DATE = {"hour": 1, "today": 2, "week": 3, "month": 4, "year": 5}
_TYPE = {"video": 1, "channel": 2, "playlist": 3, "movie": 4}
_DURATION = {"under4": 1, "plus20": 2, "between420": 3}

# Apify boolean flag -> Filters feature field number.
_FEATURES = {
    "isHD": 4,
    "hasSubtitles": 5,
    "hasCC": 6,
    "is3D": 7,
    "isLive": 8,
    "isBought": 9,
    "is4K": 14,
    "is360": 15,
    "hasLocation": 23,
    "isHDR": 25,
    "isVR180": 26,
}


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _tag_varint(field: int, value: int) -> bytes:
    """A protobuf ``field: varint`` entry (wire type 0)."""
    return _varint(field << 3) + _varint(value)


def _tag_message(field: int, data: bytes) -> bytes:
    """A protobuf ``field: message`` entry (wire type 2, length-delimited)."""
    return _varint((field << 3) | 2) + _varint(len(data)) + data


def build_search_params(input_model) -> str | None:
    """Encode the input's filters into a base64 ``sp=`` token, or ``None``.

    All set filters compose into a single protobuf; ``None`` when nothing is set
    (so the caller omits ``params`` entirely).
    """
    filters = bytearray()
    if input_model.dateFilter in _UPLOAD_DATE:
        filters += _tag_varint(1, _UPLOAD_DATE[input_model.dateFilter])
    if input_model.videoType in _TYPE:
        filters += _tag_varint(2, _TYPE[input_model.videoType])
    if input_model.lengthFilter in _DURATION:
        filters += _tag_varint(3, _DURATION[input_model.lengthFilter])
    for flag, field in _FEATURES.items():
        if getattr(input_model, flag, None):
            filters += _tag_varint(field, 1)

    message = bytearray()
    sort = _SORT_ORDER.get(input_model.sortingOrder or "")
    if sort:  # relevance (0) is the default, so it needs no bytes
        message += _tag_varint(1, sort)
    if filters:
        message += _tag_message(2, bytes(filters))

    if not message:
        return None
    return base64.b64encode(bytes(message)).decode("ascii")
