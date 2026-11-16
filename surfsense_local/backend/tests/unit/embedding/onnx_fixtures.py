"""Tiny ONNX models written as raw protobuf, since neither CI nor the app has onnx."""

from collections.abc import Sequence

import numpy as np

FLOAT, INT64, FLOAT16 = 1, 7, 10
_ATTR_INT, _ATTR_TENSOR, _ATTR_GRAPH = 2, 4, 5


def varint(value: int) -> bytes:
    """A base-128 varint, as protobuf writes integers."""
    out = bytearray()
    while True:
        low, value = value & 0x7F, value >> 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def number(field: int, value: int) -> bytes:
    """An integer field."""
    return varint(field << 3) + varint(value)


def message(field: int, payload: bytes) -> bytes:
    """A length-delimited field: a nested message, bytes or packed values."""
    return varint((field << 3) | 2) + varint(len(payload)) + payload


def text(field: int, value: str) -> bytes:
    """A string field."""
    return message(field, value.encode())


def tensor(name: str, values: np.ndarray, *, as_int32_data: bool = False) -> bytes:
    """A TensorProto; FP16 can carry its bits in int32_data instead of raw_data."""
    data_type = {np.float16: FLOAT16, np.float32: FLOAT, np.int64: INT64}[
        values.dtype.type
    ]
    dims = b"".join(number(1, d) for d in values.shape)
    if as_int32_data:
        bits = values.astype("<f2").view(np.uint16).ravel()
        data = message(5, b"".join(varint(int(b)) for b in bits))
    else:
        data = message(9, values.astype(values.dtype.newbyteorder("<")).tobytes())
    return dims + number(2, data_type) + text(8, name) + data


def value_info(name: str, elem_type: int, shape: tuple[int, ...]) -> bytes:
    """A ValueInfoProto: a graph input, output or intermediate and its tensor type."""
    dims = b"".join(message(1, number(1, d)) for d in shape)
    tensor_type = number(1, elem_type) + message(2, dims)
    return text(1, name) + message(2, message(1, tensor_type))


def attribute_int(name: str, value: int) -> bytes:
    """An INT AttributeProto, such as Cast's `to`."""
    return text(1, name) + number(20, _ATTR_INT) + number(3, value)


def attribute_tensor(name: str, value: bytes) -> bytes:
    """A TENSOR AttributeProto, such as Constant's `value`."""
    return text(1, name) + number(20, _ATTR_TENSOR) + message(5, value)


def attribute_graph(name: str, value: bytes) -> bytes:
    """A GRAPH AttributeProto: a subgraph, such as If's branches."""
    return text(1, name) + number(20, _ATTR_GRAPH) + message(6, value)


def node(
    op_type: str, inputs: list[str], outputs: list[str], *attributes: bytes
) -> bytes:
    """A NodeProto in the default domain."""
    return (
        b"".join(text(1, i) for i in inputs)
        + b"".join(text(2, o) for o in outputs)
        + text(4, op_type)
        + b"".join(message(5, a) for a in attributes)
    )


def graph(
    nodes: list[bytes],
    *,
    initializers: Sequence[bytes] = (),
    inputs: Sequence[bytes] = (),
    outputs: Sequence[bytes] = (),
    value_infos: Sequence[bytes] = (),
    sparse_initializers: Sequence[bytes] = (),
) -> bytes:
    """A GraphProto; tests pass only the parts they need."""
    return (
        b"".join(message(1, n) for n in nodes)
        + text(2, "tiny")
        + b"".join(message(5, i) for i in initializers)
        + b"".join(message(11, i) for i in inputs)
        + b"".join(message(12, o) for o in outputs)
        + b"".join(message(13, v) for v in value_infos)
        + b"".join(message(15, s) for s in sparse_initializers)
    )


def model(graph_bytes: bytes, opset: int = 17) -> bytes:
    """A ModelProto at IR 8 around one graph."""
    return number(1, 8) + message(8, number(2, opset)) + message(7, graph_bytes)


def matmul_model(dtype: type) -> bytes:
    """x @ w + b, times a Constant, plus a mask Cast to `dtype`: BGE's kinds of FP16."""
    elem = FLOAT16 if dtype is np.float16 else FLOAT
    # Values FP16 holds exactly, so the FP32 build is the FP16 one upcast.
    w = (np.arange(12).reshape(3, 4) / 10).astype(np.float16).astype(dtype)
    b = np.array([0.5, -0.25, 1.0, 2.0], dtype=dtype)
    half = np.array(0.5, dtype=dtype)
    return model(
        graph(
            [
                node(
                    "Constant",
                    [],
                    ["half"],
                    attribute_tensor("value", tensor("", half)),
                ),
                node("MatMul", ["x", "w"], ["xw"]),
                node("Add", ["xw", "b"], ["xwb"]),
                node("Mul", ["xwb", "half"], ["scaled"]),
                node("Cast", ["mask"], ["mask_cast"], attribute_int("to", elem)),
                node("Add", ["scaled", "mask_cast"], ["y"]),
            ],
            initializers=[
                tensor("w", w),
                tensor("b", b, as_int32_data=dtype is np.float16),
            ],
            inputs=[value_info("x", elem, (2, 3)), value_info("mask", INT64, (2, 4))],
            outputs=[value_info("y", elem, (2, 4))],
            value_infos=[value_info("xw", elem, (2, 4))],
        )
    )
