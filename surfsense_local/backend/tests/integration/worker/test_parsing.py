"""Real Docling on generated files, as a fresh install reads them with no network."""

import difflib
import io
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pypdfium2
import pytest
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from worker.ingestion.parser_pack import missing_parser_folders

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[3]
# The pack `pnpm dev` points the app at, then the default data dir.
PACK_ROOT = next(
    (
        root
        for root in (BACKEND / "models", Path.home() / ".surfsense" / "models")
        if not missing_parser_folders(root)
    ),
    None,
)

RECEIPT = "Harbour Cafe receipt: two flat whites and an almond croissant, 11.40 EUR."
WORDS = [
    *("revenue", "quarterly", "margin", "customer", "retention", "forecast"),
    *("inventory", "supply", "chain", "logistics", "procurement", "compliance"),
    *("audit", "regulatory", "framework", "shareholder", "dividend", "capital"),
    *("expenditure", "depreciation", "liability", "equity", "portfolio"),
    *("allocation", "benchmark", "throughput", "deployment", "migration"),
    *("resilience", "employee", "verification", "salary", "position"),
    *("department", "manager", "contract", "probation", "research"),
    *("methodology", "hypothesis", "variance", "regression", "coefficient"),
    *("correlation", "dataset"),
]

# Every file converts in one child, which pays Docling's import and model load once.
CHILD = """
import json, socket, sys

def refuse(*_args, **_kwargs):
    raise OSError("this test refuses outbound network")

# Stronger than HF_HUB_OFFLINE, which only the libraries that read it obey.
socket.socket.connect = refuse
socket.socket.connect_ex = refuse

from modules.documents.models import Document, DocumentType
from shared.db import import_models
from worker.ingestion.parsing import markdown_for

import_models()
out = {}
for document_id, name in enumerate(sys.argv[1:], start=1):
    document = Document(id=document_id, workspace_id=1, document_type=DocumentType.FILE)
    try:
        out[name] = markdown_for(document)
    except Exception as failure:
        out[name] = f"{type(failure).__name__}: {failure}"
print(json.dumps(out))
"""


def business_paragraphs(count: int, seed: int) -> list[str]:
    """Dense report prose with figures, the same for the same seed."""
    rng = random.Random(seed)
    paragraphs = []
    for _ in range(count):
        sentences = []
        for _ in range(rng.randint(3, 5)):
            words = [rng.choice(WORDS) for _ in range(rng.randint(9, 16))]
            words.insert(rng.randint(1, len(words) - 1), f"{rng.uniform(0, 100):.1f}%")
            sentences.append(words[0].capitalize() + " " + " ".join(words[1:]) + ".")
        paragraphs.append(" ".join(sentences))
    return paragraphs


def page_image(paragraphs: list[str], dpi: int) -> Image.Image:
    """The paragraphs typeset on an A4 page, rendered as a scanner would see it."""
    pdf = io.BytesIO()
    body = getSampleStyleSheet()["BodyText"]
    story = []
    for text in paragraphs:
        story += [Paragraph(text, body), Spacer(1, 8)]
    SimpleDocTemplate(pdf, pagesize=A4).build(story)
    document = pypdfium2.PdfDocument(pdf.getvalue())
    try:
        return document[0].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        document.close()


def scanned(image: Image.Image, angle: float, noise: float) -> Image.Image:
    """Skew, blur, grain and JPEG loss, like an office copier."""
    image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    image = image.filter(ImageFilter.GaussianBlur(0.4))
    pixels = np.asarray(image).astype(np.float32)
    pixels += np.random.default_rng(3).normal(0, noise, pixels.shape)
    image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
    lossy = io.BytesIO()
    image.save(lossy, "JPEG", quality=70)
    return Image.open(io.BytesIO(lossy.getvalue()))


def words(text: str) -> str:
    """The text's words and figures, without markdown or line breaks."""
    return " ".join(re.findall(r"[\w.%,:]+", text))


@pytest.fixture(scope="module")
def parsed(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Each generated file's markdown, or the error its conversion raised."""
    if PACK_ROOT is None:
        pytest.skip("run scripts/fetch_docling_models.py to exercise the real parser")

    root = tmp_path_factory.mktemp("parsing")
    files: dict[str, Image.Image | bytes] = {}

    # A phone snapshot: no DPI in the file, like most photos and screenshots.
    files["receipt.png"] = page_image([RECEIPT], 200)

    scan = scanned(page_image(business_paragraphs(5, seed=11), 200), 0.8, 10)
    scan_pdf = io.BytesIO()
    scan.save(scan_pdf, "PDF", resolution=200)
    files["scan.pdf"] = scan_pdf.getvalue()

    # Held sideways: the pixels lie on their side and EXIF says turn them upright.
    sideways = page_image([RECEIPT], 200).rotate(90, expand=True)
    exif = Image.Exif()
    exif[0x0112] = 6
    photo = io.BytesIO()
    sideways.convert("RGB").save(photo, "JPEG", quality=90, exif=exif)
    files["sideways.jpg"] = photo.getvalue()

    data_dir = root / "data"
    for document_id, (name, content) in enumerate(files.items(), start=1):
        folder = data_dir / "data" / "workspaces" / "1" / "documents" / str(document_id)
        folder.mkdir(parents=True)
        if isinstance(content, bytes):
            (folder / name).write_bytes(content)
        else:
            content.save(folder / name)

    empty_cache = root / "hf"
    empty_cache.mkdir()
    env = {
        **os.environ,
        "SURFSENSE_LOCAL_DATA_DIR": str(data_dir),
        "SURFSENSE_LOCAL_MODELS_DIR": str(PACK_ROOT),
        # A fresh install has no Hugging Face cache and every sidecar starts offline.
        "HF_HOME": str(empty_cache),
        "HF_HUB_OFFLINE": "1",
    }
    child = subprocess.run(
        [sys.executable, "-c", CHILD, *files],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=900,
    )
    assert child.returncode == 0, child.stderr[-4000:]
    return json.loads(child.stdout.strip().splitlines()[-1])


def test_an_image_is_read_offline_from_the_bundled_pack(parsed: dict[str, str]) -> None:
    """Images take the PDF path's models, so an install with no HF cache reads them."""
    assert words(RECEIPT) in words(parsed["receipt.png"])


def test_a_copier_scan_reads_back_nearly_verbatim(parsed: dict[str, str]) -> None:
    """Upright lines of a noisy scan are not flipped and misread as garbage."""
    expected = " ".join(business_paragraphs(5, seed=11))
    # autojunk off: on long text it drops common letters and the ratio means little.
    similarity = difflib.SequenceMatcher(
        None, words(expected), words(parsed["scan.pdf"]), autojunk=False
    ).ratio()

    assert similarity > 0.99


def test_a_sideways_phone_photo_reads_upright(parsed: dict[str, str]) -> None:
    """A photo stored on its side with an EXIF turn is read the way it displays."""
    assert words(RECEIPT) in words(parsed["sideways.jpg"])
