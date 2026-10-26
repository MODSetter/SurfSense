"""Every cv2 call the app's parsers make, on fixed inputs, saved to one .npz.

    python -I record_calls.py <out.npz>

check_same_outputs.py runs it under PyPI's wheel and under the minimal one. The
calls mirror their sites in rapidocr, docling, docling_ibm_models and
docling_core; RapidOCR then reads rendered text as the app configures it.
"""

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SEEDS = (0, 1, 2, 3, 4)
FONTS = (
    "arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
TEXT = (
    "SurfSense reads scanned pages",
    "Invoice 2026-10-21  Total: 1,234.56",
    "The quick brown fox jumps over the lazy dog",
)
CONSTANTS = (
    "INTER_LINEAR",
    "INTER_CUBIC",
    "INTER_NEAREST",
    "INTER_AREA",
    "BORDER_CONSTANT",
    "BORDER_REPLICATE",
    "BORDER_REFLECT",
    "BORDER_DEFAULT",
    "COLOR_GRAY2BGR",
    "COLOR_RGB2BGR",
    "COLOR_RGBA2BGRA",
    "ROTATE_180",
    "RETR_LIST",
    "CHAIN_APPROX_SIMPLE",
    "FONT_HERSHEY_SIMPLEX",
)

outputs: dict[str, np.ndarray] = {}


def put(name: str, value: object) -> None:
    """Flatten tuples and lists of results into one array per leaf."""
    if isinstance(value, (tuple, list)) and not (
        value and all(isinstance(v, (int, float)) for v in value)
    ):
        put(f"{name}/len", np.array(len(value)))
        for index, item in enumerate(value):
            put(f"{name}/{index}", item)
    elif isinstance(value, (bytes, str)):
        data = value.encode() if isinstance(value, str) else value
        outputs[name] = np.frombuffer(data, dtype=np.uint8)
    else:
        outputs[name] = np.asarray(value)


def images(seed: int) -> dict[str, np.ndarray]:
    """Noise, and a page-like picture of soft blobs and edges, in each layout used.

    Sizes move with the seed, so rows end at every offset from a SIMD width.
    """
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, (375 + 7 * seed, 500 + 13 * seed, 3), dtype=np.uint8)
    h, w = 420 + 5 * seed, 560 + 11 * seed
    y, x = np.mgrid[0:h, 0:w]
    page = np.full((h, w), 235.0)
    for cx, cy, r in rng.uniform((0, 0, 15), (w, h, 70), (12, 3)):
        page -= 180 * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * r * r))
    page += rng.normal(0, 6, page.shape)
    gray = np.clip(page, 0, 255).astype(np.uint8)
    rgb = np.stack([gray, np.roll(gray, 7, axis=1), np.roll(gray, 5, axis=0)], -1)
    alpha = rng.integers(0, 256, gray.shape, dtype=np.uint8)
    return {
        "noise": noise,
        "rgb": np.ascontiguousarray(rgb),
        "gray": gray,
        "rgba": np.dstack([rgb, alpha]),
        "float": rgb.astype(np.float32) / 255,
    }


def record_resize(name: str, image: np.ndarray) -> None:
    h, w = image.shape[:2]
    for size in ((w // 3, h // 3), (int(w * 1.3), int(h * 1.2)), (321, 48)):
        put(f"{name}/resize/default/{size}", cv2.resize(image, size))
        for inter in ("INTER_LINEAR", "INTER_CUBIC", "INTER_NEAREST", "INTER_AREA"):
            resized = cv2.resize(image, dsize=size, interpolation=getattr(cv2, inter))
            put(f"{name}/resize/{inter}/{size}", resized)


def record_geometry(name: str, image: np.ndarray, rng: np.random.Generator) -> None:
    h, w = image.shape[:2]
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    points = (corners * 0.6 + rng.uniform(5, 60, (4, 2))).astype(np.float32)
    crop_w, crop_h = 300, 64
    standard = np.float32([[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]])
    matrix = cv2.getPerspectiveTransform(points, standard)
    put(f"{name}/getPerspectiveTransform", matrix)
    put(f"{name}/invert", cv2.invert(matrix))
    for flags in (cv2.INTER_CUBIC, cv2.INTER_LINEAR):
        warped = cv2.warpPerspective(
            image,
            matrix,
            (crop_w, crop_h),
            borderMode=cv2.BORDER_REPLICATE,
            flags=flags,
        )
        put(f"{name}/warpPerspective/{flags}", warped)
    for border in (
        "BORDER_CONSTANT",
        "BORDER_REPLICATE",
        "BORDER_REFLECT",
        "BORDER_DEFAULT",
    ):
        padded = cv2.copyMakeBorder(
            image, 3, 9, 0, 17, getattr(cv2, border), value=(0, 0, 0)
        )
        put(f"{name}/copyMakeBorder/{border}", padded)
    put(f"{name}/rotate/ROTATE_180", cv2.rotate(image, cv2.ROTATE_180))
    put(f"{name}/rotate/1", cv2.rotate(image, 1))


def record_detection(name: str, gray: np.ndarray) -> None:
    """RapidOCR's det post-processing and Docling's OCR mask, on a thresholded page."""
    probability = gray.astype(np.float32) / 255
    bitmap = probability < 0.6
    put(
        f"{name}/dilate/2x2",
        cv2.dilate(bitmap.astype(np.uint8), np.array([[1, 1], [1, 1]])),
    )
    kernel = np.ones((3, 3), dtype=np.uint8)
    put(
        f"{name}/dilate/3x3",
        cv2.dilate((gray < 150).astype(np.uint8), kernel, iterations=1),
    )
    contours, hierarchy = cv2.findContours(
        (bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    put(f"{name}/findContours", (contours, hierarchy))
    for index, contour in enumerate(contours[:200]):
        box = cv2.minAreaRect(contour)
        put(f"{name}/minAreaRect/{index}", box)
        corners = cv2.boxPoints(box)
        put(f"{name}/boxPoints/{index}", corners)
        xmin = int(np.clip(np.floor(corners[:, 0].min()), 0, gray.shape[1] - 1))
        xmax = int(np.clip(np.ceil(corners[:, 0].max()), 0, gray.shape[1] - 1))
        ymin = int(np.clip(np.floor(corners[:, 1].min()), 0, gray.shape[0] - 1))
        ymax = int(np.clip(np.ceil(corners[:, 1].max()), 0, gray.shape[0] - 1))
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        shifted = corners - [xmin, ymin]
        cv2.fillPoly(mask, shifted.reshape(1, -1, 2).astype(np.int32), 1)
        put(f"{name}/fillPoly/{index}", mask)
        region = probability[ymin : ymax + 1, xmin : xmax + 1]
        put(f"{name}/mean/{index}", cv2.mean(region, mask))


def record_colour_and_codecs(name: str, rgb: np.ndarray, rgba: np.ndarray) -> None:
    gray = rgb[..., 0].copy()
    put(f"{name}/cvtColor/GRAY2BGR", cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
    put(f"{name}/cvtColor/RGB2BGR", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    put(f"{name}/cvtColor/RGBA2BGRA", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    # RapidOCR's RGBA load: alpha over white.
    alpha = rgba[..., 3]
    not_alpha = cv2.bitwise_not(alpha)
    not_alpha = cv2.cvtColor(not_alpha, cv2.COLOR_GRAY2BGR)
    bgr = cv2.cvtColor(rgba[..., :3].copy(), cv2.COLOR_RGB2BGR)
    blended = cv2.bitwise_and(bgr, bgr, mask=alpha)
    put(f"{name}/bitwise_not", not_alpha)
    put(f"{name}/bitwise_and", blended)
    put(f"{name}/add", cv2.add(blended, not_alpha))
    for image, label in ((rgb, "bgr"), (gray, "gray"), (rgba, "bgra")):
        for ext in (".png", ".jpg"):
            ok, encoded = cv2.imencode(ext, image)
            put(f"{name}/imencode/{label}{ext}", (np.array(ok), encoded))
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / f"out{ext}"
                put(
                    f"{name}/imwrite/{label}{ext}",
                    np.array(cv2.imwrite(str(path), image)),
                )
                put(f"{name}/imwrite/{label}{ext}/bytes", path.read_bytes())


def record_drawing(name: str, rgb: np.ndarray) -> None:
    """RapidOCR's visualiser: boxes and their scores drawn on a copy."""
    canvas = rgb.copy()
    box = np.array([[20.4, 30.2], [260.9, 28.7], [262.1, 80.5], [19.6, 82.3]])
    cv2.polylines(canvas, np.int32([box]), 1, color=(0, 0, 255), thickness=1)
    cv2.putText(
        canvas, "0:0.987", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 1
    )
    put(f"{name}/polylines+putText", canvas)
    put(f"{name}/Mat", np.asarray(cv2.Mat(rgb)))


def text_page(upside_down: bool) -> np.ndarray:
    image = Image.new("RGB", (1400, 420), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(TEXT):
        draw.text((40, 40 + row * 120), line, fill=(0, 0, 0), font=_font())
    if upside_down:
        image = image.rotate(180)
    return np.asarray(image)


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in FONTS:
        try:
            return ImageFont.truetype(name, 56)
        except OSError:
            continue
    return ImageFont.load_default(size=56)


def record_rapidocr(prefix: str) -> None:
    """The app's RapidOCR settings, then with every cv2-using stage on."""
    import rapidocr
    from rapidocr import RapidOCR

    models = Path(rapidocr.__file__).parent / "models"
    app = {
        "Global.text_score": 0.5,
        "Global.use_cls": False,
        "Global.log_level": "error",
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "Det.model_path": str(models / "PP-OCRv6_det_small.onnx"),
        "Rec.model_path": str(models / "PP-OCRv6_rec_small.onnx"),
        "Cls.model_path": str(models / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"),
    }
    every_stage = {**app, "Global.use_cls": True}
    for label, params in (("app", app), ("every-stage", every_stage)):
        engine = RapidOCR(params=params)
        for upside_down in (False, True):
            page = text_page(upside_down)
            name = f"{prefix}/rapidocr/{label}/{'upside-down' if upside_down else 'upright'}"
            put(f"{name}/page", page)
            word_boxes = label == "every-stage"
            result = engine(page, return_word_box=word_boxes)
            put(f"{name}/boxes", result.boxes)
            put(f"{name}/txts", "\n".join(result.txts or ()))
            put(f"{name}/scores", np.array(result.scores, dtype=np.float64))
            if word_boxes:
                put(f"{name}/word_results", repr(result.word_results))


def record_every_call(prefix: str) -> None:
    put(f"{prefix}/ocl/useOpenCL", np.array(cv2.ocl.useOpenCL()))
    for seed in SEEDS:
        rng = np.random.default_rng(100 + seed)
        made = images(seed)
        name = f"{prefix}/{seed}"
        for label, image in made.items():
            record_resize(f"{name}/{label}", image)
            if label != "rgba":
                record_geometry(f"{name}/{label}", image, rng)
        record_detection(f"{name}/page", made["gray"])
        record_colour_and_codecs(f"{name}/page", made["rgb"], made["rgba"])
        record_colour_and_codecs(f"{name}/noise", made["noise"], made["rgba"])
        record_drawing(f"{name}/page", made["rgb"])
    record_rapidocr(prefix)


def main() -> None:
    put("version", cv2.__version__)
    put("constants", np.array([getattr(cv2, name) for name in CONSTANTS]))
    # Scan OCR runs RapidOCR on cv2's defaults; inside Docling,
    # docling_ibm_models has set both on import.
    record_every_call("defaults")
    cv2.setNumThreads(0)
    cv2.ocl.setUseOpenCL(False)
    record_every_call("one-thread")
    np.savez_compressed(sys.argv[1], **outputs)
    print(f"{len(outputs)} outputs from cv2 {cv2.__version__} in {sys.argv[1]}")


if __name__ == "__main__":
    main()
