"""An FP16 model rewritten as FP32 in memory, or refused whole."""

import numpy as np
import onnxruntime as ort
import pytest

from modules.embedding.fp32_upcast import UnsupportedModelError, upcast
from tests.unit.embedding import onnx_fixtures as wire

pytestmark = pytest.mark.unit

X = np.array([[1.0, 2.0, 3.0], [-1.0, 0.5, 0.25]])
MASK = np.array([[1, 1, 0, 1], [0, 1, 1, 1]], dtype=np.int64)


def _session(model: bytes) -> ort.InferenceSession:
    return ort.InferenceSession(model, providers=["CPUExecutionProvider"])


def _run(model: bytes, dtype: type) -> np.ndarray:
    return _session(model).run(None, {"x": X.astype(dtype), "mask": MASK})[0]


def test_an_fp16_model_becomes_the_same_model_at_fp32() -> None:
    """Initializers in raw_data and in int32_data, a Constant, a Cast target and
    every declared type: the result is the graph as it would be built at FP32."""
    fp16 = wire.matmul_model(np.float16)

    upcast_model = upcast(fp16)

    session = _session(upcast_model)
    assert [i.type for i in session.get_inputs()] == ["tensor(float)", "tensor(int64)"]
    assert [o.type for o in session.get_outputs()] == ["tensor(float)"]
    result = _run(upcast_model, np.float32)
    assert result.dtype == np.float32
    np.testing.assert_array_equal(
        result, _run(wire.matmul_model(np.float32), np.float32)
    )
    np.testing.assert_allclose(
        result, _run(fp16, np.float16).astype(np.float32), rtol=1e-3, atol=1e-3
    )


def test_an_upcast_model_has_no_fp16_left() -> None:
    """Upcasting it again finds nothing to change."""
    upcast_model = upcast(wire.matmul_model(np.float16))

    assert upcast(upcast_model) is upcast_model


def test_a_model_with_no_fp16_comes_back_untouched() -> None:
    """The very bytes it was given, not a re-encoding of them."""
    fp32 = wire.matmul_model(np.float32)

    assert upcast(fp32) is fp32


def _external_weights() -> bytes:
    location = wire.text(1, "location") + wire.text(2, "w.bin")
    w = (
        wire.number(1, 3)
        + wire.number(1, 4)
        + wire.number(2, wire.FLOAT16)
        + wire.text(8, "w")
        + wire.message(13, location)
        + wire.number(14, 1)
    )
    return wire.model(
        wire.graph([wire.node("MatMul", ["x", "w"], ["y"])], initializers=[w])
    )


def _sparse_initializer() -> bytes:
    values = wire.tensor("s", np.array([1.0, 2.0], dtype=np.float16))
    indices = wire.tensor("", np.array([0, 3], dtype=np.int64))
    sparse = wire.message(1, values) + wire.message(2, indices) + wire.number(3, 4)
    return wire.model(wire.graph([], sparse_initializers=[sparse]))


def _subgraph() -> bytes:
    branch = wire.graph([wire.node("Identity", ["x"], ["y"])])
    if_node = wire.node(
        "If",
        ["condition"],
        ["y"],
        wire.attribute_graph("then_branch", branch),
        wire.attribute_graph("else_branch", branch),
    )
    return wire.model(wire.graph([if_node]))


def _fp16_type_attribute(op_type: str, name: str) -> bytes:
    typed = wire.node(op_type, ["x"], ["y"], wire.attribute_int(name, wire.FLOAT16))
    return wire.model(wire.graph([typed]))


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(_external_weights(), id="external-data"),
        pytest.param(_sparse_initializer(), id="sparse-initializer"),
        pytest.param(_subgraph(), id="subgraph"),
        pytest.param(_fp16_type_attribute("EyeLike", "dtype"), id="eyelike-dtype"),
        pytest.param(
            _fp16_type_attribute("LayerNormalization", "stash_type"),
            id="layernorm-stash-type",
        ),
        pytest.param(
            _fp16_type_attribute("MelWeightMatrix", "output_datatype"),
            id="melweightmatrix-output-datatype",
        ),
        pytest.param(wire.matmul_model(np.float16)[:-3], id="truncated"),
    ],
)
def test_what_it_cannot_rewrite_whole_is_refused(model: bytes) -> None:
    """The caller then opens the file as shipped, never a half-FP16 model."""
    with pytest.raises(UnsupportedModelError):
        upcast(model)
