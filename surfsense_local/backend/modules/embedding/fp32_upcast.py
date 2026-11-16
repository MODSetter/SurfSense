"""An FP16 ONNX model rewritten as FP32, in memory.

The frozen app has onnxruntime and numpy but not the onnx package, so this edits
the protobuf wire format directly. It refuses any part it cannot rewrite whole,
rather than return a model that is only partly FP32.
"""

from collections.abc import Iterator

import numpy as np

FLOAT = 1
FLOAT16 = 10

_VARINT, _FIXED64, _LENGTH, _FIXED32 = 0, 1, 2, 5

# Field numbers from onnx.proto.
_MODEL_GRAPH, _MODEL_TRAINING_INFO, _MODEL_FUNCTIONS = 7, 20, 25
_GRAPH_NODE, _GRAPH_INITIALIZER, _GRAPH_SPARSE_INITIALIZER = 1, 5, 15
_GRAPH_VALUE_INFOS = frozenset({11, 12, 13})  # input, output, value_info
_NODE_OP_TYPE, _NODE_ATTRIBUTE, _NODE_DOMAIN = 4, 5, 7
_ATTR_NAME, _ATTR_I, _ATTR_T, _ATTR_TENSORS = 1, 3, 5, 10
_ATTR_TYPE_PROTOS = frozenset({14, 15})
_ATTR_SUBGRAPHS = frozenset({6, 11})
_ATTR_SPARSE = frozenset({22, 23})
_TENSOR_DIMS, _TENSOR_DATA_TYPE, _TENSOR_SEGMENT, _TENSOR_INT32_DATA = 1, 2, 3, 5
_TENSOR_RAW_DATA, _TENSOR_EXTERNAL_DATA, _TENSOR_DATA_LOCATION = 9, 13, 14
_VALUE_INFO_TYPE = 2
_TYPE_TENSOR, _TYPE_SEQUENCE, _TYPE_MAP, _TYPE_SPARSE, _TYPE_OPTIONAL = 1, 4, 5, 8, 9
_ELEM_TYPE, _MAP_VALUE_TYPE = 1, 2

# Integer attributes that name a data type: Cast's `to`, and by ONNX's naming every
# `dtype`, `output_datatype` or `stash_type`. Only Cast's is known safe to change.
_CAST_TARGET = b"to"
_DTYPE_SUFFIX = b"type"

Field = tuple[int, int, int | bytes | memoryview]


class UnsupportedModelError(ValueError):
    """The model holds something this rewrite cannot carry to FP32 or out of a file."""


def upcast(model: bytes) -> bytes:
    """The model with every FLOAT16 tensor, type and Cast target made FLOAT.

    Returns `model` itself when it holds no FLOAT16.
    """
    rewrite = _Upcast()
    upcast_model = rewrite.model(memoryview(model))
    return upcast_model if rewrite.changes else model


class _Upcast:
    def __init__(self) -> None:
        self.changes = 0

    def model(self, message: memoryview) -> bytes:
        out: list[Field] = []
        for number, wire, value in _fields(message):
            if number == _MODEL_TRAINING_INFO:
                raise UnsupportedModelError("training graphs are not rewritten")
            if number == _MODEL_FUNCTIONS:
                raise UnsupportedModelError("model-local functions are not rewritten")
            if number == _MODEL_GRAPH and wire == _LENGTH:
                value = self.graph(_view(value))
            out.append((number, wire, value))
        return _build(out)

    def graph(self, message: memoryview) -> bytes:
        out: list[Field] = []
        for number, wire, value in _fields(message):
            if number == _GRAPH_SPARSE_INITIALIZER:
                raise UnsupportedModelError("sparse initializers are not rewritten")
            if wire == _LENGTH:
                if number == _GRAPH_NODE:
                    value = self.node(_view(value))
                elif number == _GRAPH_INITIALIZER:
                    value = self.tensor(_view(value))
                elif number in _GRAPH_VALUE_INFOS:
                    value = self.value_info(_view(value))
            out.append((number, wire, value))
        return _build(out)

    def node(self, message: memoryview) -> bytes:
        items = list(_fields(message))
        op_type = _string(items, _NODE_OP_TYPE)
        domain = _string(items, _NODE_DOMAIN)
        is_cast = op_type == b"Cast" and domain in (b"", b"ai.onnx")
        return _build(
            [
                (number, wire, self.attribute(_view(value), is_cast))
                if number == _NODE_ATTRIBUTE and wire == _LENGTH
                else (number, wire, value)
                for number, wire, value in items
            ]
        )

    def attribute(self, message: memoryview, is_cast: bool) -> bytes:
        items = list(_fields(message))
        name = _string(items, _ATTR_NAME)
        out: list[Field] = []
        for number, wire, value in items:
            if number in _ATTR_SUBGRAPHS:
                raise UnsupportedModelError("graphs with subgraphs are not rewritten")
            if number in _ATTR_SPARSE:
                raise UnsupportedModelError("sparse tensors are not rewritten")
            if number in (_ATTR_T, _ATTR_TENSORS) and wire == _LENGTH:
                value = self.tensor(_view(value))
            elif number in _ATTR_TYPE_PROTOS and wire == _LENGTH:
                value = self.type_proto(_view(value))
            elif (
                number == _ATTR_I
                and wire == _VARINT
                and value == FLOAT16
                and (name == _CAST_TARGET or name.endswith(_DTYPE_SUFFIX))
            ):
                if not (is_cast and name == _CAST_TARGET):
                    raise UnsupportedModelError(
                        f"an FP16 '{name.decode(errors='replace')}' attribute outside "
                        "Cast is not rewritten"
                    )
                value = FLOAT
                self.changes += 1
            out.append((number, wire, value))
        return _build(out)

    def tensor(self, message: memoryview) -> bytes:
        items = list(_fields(message))
        for number, _wire, value in items:
            if number == _TENSOR_EXTERNAL_DATA or (
                number == _TENSOR_DATA_LOCATION and value != 0
            ):
                raise UnsupportedModelError("external data cannot load from bytes")
        if _last(items, _TENSOR_DATA_TYPE) != FLOAT16:
            return bytes(message)
        if any(number == _TENSOR_SEGMENT for number, _w, _v in items):
            raise UnsupportedModelError("segmented tensors are not rewritten")

        values = _fp16_values(items)
        count = 1
        for dim in _varints(items, _TENSOR_DIMS):
            if dim >= 1 << 63:
                raise UnsupportedModelError("a tensor has a negative dimension")
            count *= dim
        if values.size != count:
            raise UnsupportedModelError("a tensor's data does not match its shape")

        kept = [
            field
            for field in items
            if field[0] not in (_TENSOR_DATA_TYPE, _TENSOR_INT32_DATA, _TENSOR_RAW_DATA)
        ]
        kept.append((_TENSOR_DATA_TYPE, _VARINT, FLOAT))
        kept.append((_TENSOR_RAW_DATA, _LENGTH, memoryview(values.astype("<f4"))))
        self.changes += 1
        return _build(kept)

    def value_info(self, message: memoryview) -> bytes:
        return _build(
            [
                (number, wire, self.type_proto(_view(value)))
                if number == _VALUE_INFO_TYPE and wire == _LENGTH
                else (number, wire, value)
                for number, wire, value in _fields(message)
            ]
        )

    def type_proto(self, message: memoryview) -> bytes:
        out: list[Field] = []
        for number, wire, value in _fields(message):
            if wire == _LENGTH:
                if number in (_TYPE_TENSOR, _TYPE_SPARSE):
                    value = self._elem_type(_view(value))
                elif number in (_TYPE_SEQUENCE, _TYPE_OPTIONAL):
                    value = self._nested_type(_view(value), _ELEM_TYPE)
                elif number == _TYPE_MAP:
                    value = self._nested_type(_view(value), _MAP_VALUE_TYPE)
            out.append((number, wire, value))
        return _build(out)

    def _elem_type(self, message: memoryview) -> bytes:
        out: list[Field] = []
        for number, wire, value in _fields(message):
            if number == _ELEM_TYPE and wire == _VARINT and value == FLOAT16:
                value = FLOAT
                self.changes += 1
            out.append((number, wire, value))
        return _build(out)

    def _nested_type(self, message: memoryview, type_field: int) -> bytes:
        return _build(
            [
                (number, wire, self.type_proto(_view(value)))
                if number == type_field and wire == _LENGTH
                else (number, wire, value)
                for number, wire, value in _fields(message)
            ]
        )


def _fp16_values(items: list[Field]) -> np.ndarray:
    """FP16 values sit in raw_data, or as one uint16 per int32_data entry."""
    raw = [value for number, _wire, value in items if number == _TENSOR_RAW_DATA]
    has_int32 = any(number == _TENSOR_INT32_DATA for number, _w, _v in items)
    if raw and has_int32:
        raise UnsupportedModelError("a tensor holds both raw_data and int32_data")
    if raw:
        data = _view(raw[-1])
        if len(data) % 2:
            raise UnsupportedModelError("FP16 raw_data has an odd length")
        return np.frombuffer(data, dtype="<f2")
    bits = list(_varints(items, _TENSOR_INT32_DATA))
    if any(b > 0xFFFF for b in bits):
        raise UnsupportedModelError("FP16 int32_data holds a value over 16 bits")
    return np.array(bits, dtype=np.uint16).view("<f2")


def _varints(items: list[Field], wanted: int) -> Iterator[int]:
    """A repeated integer field's values, packed or not."""
    for number, wire, value in items:
        if number != wanted:
            continue
        if wire == _VARINT:
            yield _int(value)
        elif wire == _LENGTH:
            packed = _view(value)
            at = 0
            while at < len(packed):
                decoded, at = _read_varint(packed, at)
                yield decoded
        else:
            raise UnsupportedModelError(f"field {wanted} has wire type {wire}")


def _string(items: list[Field], wanted: int) -> bytes:
    found = [value for number, wire, value in items if number == wanted]
    return bytes(_view(found[-1])) if found else b""


def _last(items: list[Field], wanted: int) -> int | None:
    found = [value for number, wire, value in items if number == wanted]
    return _int(found[-1]) if found else None


def _fields(message: memoryview) -> Iterator[Field]:
    at, end = 0, len(message)
    while at < end:
        key, at = _read_varint(message, at)
        number, wire = key >> 3, key & 7
        if wire == _VARINT:
            value, at = _read_varint(message, at)
            yield number, wire, value
            continue
        if wire == _LENGTH:
            size, at = _read_varint(message, at)
        elif wire == _FIXED64:
            size = 8
        elif wire == _FIXED32:
            size = 4
        else:
            raise UnsupportedModelError(f"wire type {wire} is not used by ONNX")
        if at + size > end:
            raise UnsupportedModelError("the model is truncated")
        yield number, wire, message[at : at + size]
        at += size


def _read_varint(data: memoryview, at: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        if at >= len(data) or shift > 63:
            raise UnsupportedModelError("the model has a malformed varint")
        byte = data[at]
        at += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, at


def _write_varint(value: int) -> bytes:
    if value < 0:
        value += 1 << 64
    out = bytearray()
    while True:
        low, value = value & 0x7F, value >> 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def _build(fields: list[Field]) -> bytes:
    parts: list[bytes | memoryview] = []
    for number, wire, value in fields:
        parts.append(_write_varint((number << 3) | wire))
        if wire == _VARINT:
            parts.append(_write_varint(_int(value)))
        else:
            data = _view(value)
            if wire == _LENGTH:
                parts.append(_write_varint(len(data)))
            parts.append(data)
    return b"".join(parts)


def _view(value: int | bytes | memoryview) -> memoryview:
    if isinstance(value, int):
        raise UnsupportedModelError("a message field holds a varint")
    return memoryview(value).cast("B")


def _int(value: int | bytes | memoryview) -> int:
    if not isinstance(value, int):
        raise UnsupportedModelError("an integer field holds bytes")
    return value
