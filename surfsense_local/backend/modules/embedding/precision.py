"""Whether the bundled bge runs as shipped, at FP16, or upcast to FP32.

On x86-64, ONNX Runtime's CPU MatMul takes FP16 through a slow kernel: 2.0
passages/s against 11.6 upcast (Ryzen 5800X, 8 threads; 4.1x at 4, 2.2x at 1),
with cosine >= 0.9999995 between the two and the same top-1 on 266 of 266 eval
queries.
"""

import logging
import sysconfig
from enum import StrEnum

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from modules.embedding.bundled import is_bundled
from modules.embedding.spec import EmbedderSpec

log = logging.getLogger(__name__)

# The interpreter's build, which onnxruntime's matches: an x64 build emulated on
# Windows on ARM still takes the slow FP16 path, though platform.machine() says ARM64.
_X86_64_BUILDS = ("amd64", "x86_64")


class Precision(StrEnum):
    # FP32 on x86-64 only: Apple silicon runs the FP16 file at 14.5 chunk-sized
    # passages/s already, and the upcast was never measured there.
    AUTO = "auto"
    FP16 = "fp16"
    FP32 = "fp32"


class PrecisionSettings(BaseSettings):
    """SURFSENSE_LOCAL_EMBED_PRECISION, an escape hatch should the upcast misbehave."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    embed_precision: Precision = Precision.AUTO

    @field_validator("embed_precision", mode="before")
    @classmethod
    def _any_case(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


def runs_at_fp32(spec: EmbedderSpec) -> bool:
    """Only the bundled bge: its upcast is the one measured to keep its vectors."""
    if not is_bundled(spec):
        return False
    precision = _chosen()
    if precision is Precision.AUTO:
        return sysconfig.get_platform().lower().endswith(_X86_64_BUILDS)
    return precision is Precision.FP32


def _chosen() -> Precision:
    # Not cached: it is read once per session load, and encoder._loaded caches those.
    try:
        return PrecisionSettings().embed_precision
    except ValidationError:
        # Whoever set the switch most likely meant to turn the upcast off.
        log.warning("SURFSENSE_LOCAL_EMBED_PRECISION is not auto, fp16 or fp32: fp16")
        return Precision.FP16
