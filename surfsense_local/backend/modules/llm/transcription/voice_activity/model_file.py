"""Silero VAD's 16 kHz ONNX build (MIT), pinned by commit and hash, staged into
the models pack by `scripts/fetch_silero_vad.py` and read there in place."""

from dataclasses import dataclass
from pathlib import Path

from shared.config import get_storage_settings

__all__ = [
    "SILERO_VAD",
    "VAD_DIR_NAME",
    "PinnedVad",
    "silero_vad_dir",
    "silero_vad_file",
]

VAD_DIR_NAME = "silero-vad"


@dataclass(frozen=True)
class PinnedFile:
    path: str
    sha256: str

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class PinnedVad:
    repo: str
    commit: str
    weights: PinnedFile
    # MIT asks for its notice beside every copy.
    licence: PinnedFile


SILERO_VAD = PinnedVad(
    repo="snakers4/silero-vad",
    # v6.2.3. A commit and checksums, public by nature: not secrets.
    # pragma: allowlist nextline secret
    commit="5cd7945676eb32225748052e2e6a0580e4686a08",
    weights=PinnedFile(
        # 1,289,603 B: opset 15, 16 kHz only.
        path="src/silero_vad/data/silero_vad_16k_op15.onnx",
        # pragma: allowlist nextline secret
        sha256="7ed98ddbad84ccac4cd0aeb3099049280713df825c610a8ed34543318f1b2c49",
    ),
    licence=PinnedFile(
        path="LICENSE",
        # pragma: allowlist nextline secret
        sha256="2e63e9a38b6e8fc0c7bc37ce174caca1862870856c6daf5697cfb785e925520b",
    ),
)


def silero_vad_dir() -> Path:
    return get_storage_settings().models_dir / VAD_DIR_NAME


def silero_vad_file() -> Path:
    return silero_vad_dir() / SILERO_VAD.weights.name
