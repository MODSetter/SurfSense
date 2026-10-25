"""Files the hooks collect that nothing in the app ever opens.

Each rule names its file by its destination in the bundle, so a version bump
that renames the file fails a packaging test rather than shipping it again.
"""

import sys
from fnmatch import fnmatch


def _dropped(destination: str) -> bool:
    path = destination.replace("\\", "/")
    name = path.rsplit("/", 1)[-1].lower()
    # RapidOCR's wheel carries its own copy of the OCR models; the app and Docling
    # read only the parser pack's (worker/ingestion/scan_ocr/rapid.py,
    # parsing.py's artifacts_path).
    if path.startswith("rapidocr/models/") and name.endswith(".onnx"):
        return True
    # onnxruntime's C API library, for C callers; Python loads the pybind module,
    # which links none of it.
    if path.startswith("onnxruntime/capi/") and (
        name == "onnxruntime.dll"
        or fnmatch(name, "libonnxruntime.*.dylib")
        or fnmatch(name, "libonnxruntime.so*")
    ):
        return True
    # torch's protobuf compiler, for building extensions.
    if path.startswith("torch/bin/") and name.startswith("protoc"):
        return True
    if sys.platform == "win32":
        # OpenCV's FFmpeg video plugin: RapidOCR, Docling and TableFormer only
        # decode images. On macOS and Linux FFmpeg is linked into cv2 itself.
        return path.startswith("cv2/") and name.startswith("opencv_videoio_ffmpeg")
    if sys.platform == "linux":
        # The Linux CPU wheel's C++ tests and their libraries. torch_shm_manager
        # stays: `import torch` refuses to start without it.
        if path.startswith("torch/test/"):
            return True
        if path.startswith("torch/bin/") and name != "torch_shm_manager":
            return True
        return path.startswith("torch/lib/") and name in {
            "libtorchbind_test.so",
            "libjitbackend_test.so",
            "libbackend_with_compiler.so",
            "libaoti_custom_ops.so",
        }
    return False


def without_unused_payload(entries: list) -> list:
    """A TOC (binaries or datas) minus the files above."""
    return [entry for entry in entries if not _dropped(entry[0])]
