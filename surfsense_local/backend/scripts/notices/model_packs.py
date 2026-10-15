"""Notices for the model packs the installer bundles, named from their pins.

Most packs ship no licence file upstream, so each carries the licence id its
model card declares and says plainly that no text ships, rather than invent one.
Silero VAD stages its own LICENSE beside the weights, so its text ships.
"""

from importlib.metadata import version
from pathlib import Path

from fetch_bundled_voice import shipped_build

from modules.embedding.bundled import BGE
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.transcription.voice_activity.model_file import (
    SILERO_VAD,
    VAD_DIR_NAME,
)
from worker.ingestion.parser_pack import PARSER_FOLDERS

NO_TEXT = "Only the licence id is known; no licence text ships with the weights."

# Licence ids from each Hugging Face model card, checked when this was written.
BGE_LICENCE = "mit"
PARSER_LICENCES = {
    "docling-project--docling-layout-heron": "apache-2.0",
    # The card lists both: the TableFormer weights' data licence and the code's.
    "docling-project--docling-models": "cdla-permissive-2.0, apache-2.0",
    "RapidOcr": "apache-2.0",
}
PARSER_SOURCES = {"RapidOcr": "RapidAI's RapidOCR ONNX models (PaddleOCR-derived)"}


def _entry(name: str, revision: str, licence: str, source: str) -> dict[str, str]:
    return {
        "name": name,
        "version": revision,
        "tree": "model",
        "license": licence,
        "text": "",
        "note": f"{source}. {NO_TEXT}",
    }


def _embedder() -> dict[str, str]:
    source = f"Weights from {BGE.repo} on Hugging Face at revision {BGE.revision}"
    return _entry(BGE.id, BGE.revision, BGE_LICENCE, source)


def _voice() -> dict[str, str]:
    models = load_local_manifest().models
    build = shipped_build(models)
    model = next(m for m in models if build in m.as_builds())
    weights = build.weights
    source = f"{weights.path} from {weights.repo} on Hugging Face at revision {weights.revision}"
    return _entry(model.name, weights.revision, model.license, source)


def _parser() -> list[dict[str, str]]:
    # Docling's downloader pins the revisions, so its version pins the pack.
    docling = version("docling")
    entries = []
    for folder in PARSER_FOLDERS:
        repo = PARSER_SOURCES.get(folder, folder.replace("--", "/"))
        source = f"{repo}, as Docling {docling} downloads it"
        entries.append(
            _entry(folder, f"docling {docling}", PARSER_LICENCES[folder], source)
        )
    return entries


def _vad(models_root: Path) -> dict[str, str]:
    """The staged LICENSE, which fetch_silero_vad.py checks by its pinned hash."""
    source = f"{SILERO_VAD.weights.path} from {SILERO_VAD.repo} at {SILERO_VAD.commit}"
    licence = models_root / VAD_DIR_NAME / SILERO_VAD.licence.name
    if not licence.is_file():
        entry = _entry("Silero VAD", SILERO_VAD.commit, "mit", source)
        entry["note"] = f"{source}. Its LICENSE is not staged in {models_root}."
        return entry
    entry = _entry("Silero VAD", SILERO_VAD.commit, "mit", source)
    entry["text"] = licence.read_text(encoding="utf-8")
    entry["note"] = f"{source}, with its LICENSE."
    return entry


def model_notices(models_root: Path = Path("models")) -> list[dict[str, str]]:
    """`models_root` is where build:vad stages the packs: backend/models."""
    return [_embedder(), _voice(), *_parser(), _vad(models_root)]
