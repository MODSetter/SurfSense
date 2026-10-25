"""What the worker role carries that PyInstaller's analyser cannot follow.

Ingest embeds chunks (onnxruntime) and parses files (Docling, which pulls torch
and RapidOCR). torch is picked up by PyInstaller's own hook; the packages below
are collected because their data or native libs are reached by path or by
string.
"""

import sys

from common import BACKEND, database_inputs
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# Docling's layout engine loads RT-DETR v2 through these, by name (Auto*), so
# the analyser cannot follow them; tokenization_auto imports encoder_decoder.
# Every other transformers model is excluded (excluded_modules.unused_transformers_models).
TRANSFORMERS_MODELS_USED = ("auto", "rt_detr", "rt_detr_v2", "encoder_decoder")


def worker_inputs() -> tuple[list, list, list]:
    """(datas, binaries, hiddenimports) the worker role needs in the bundle."""
    datas, binaries, hiddenimports = database_inputs()

    # The worker reaches parse_models through studio/job.py -> openai_compatible ->
    # chat.py, so it needs the remote model manifest the API also ships.
    datas.append(
        (
            str(
                BACKEND
                / "modules"
                / "llm"
                / "catalog"
                / "remote"
                / "manifest"
                / "models.json"
            ),
            "modules/llm/catalog/remote/manifest",
        )
    )
    # Studio resolves its chosen image and audio models through the local catalog,
    # which knows a curated model only from this manifest; without it an installed,
    # chosen model reads as "not installed".
    datas.append(
        (
            str(
                BACKEND
                / "modules"
                / "llm"
                / "catalog"
                / "local"
                / "manifest"
                / "models.json"
            ),
            "modules/llm/catalog/local/manifest",
        )
    )
    # Studio's Word and PDF path follows the measured level; without the list a
    # frozen build drafts every remote model by script and every local one by Markdown.
    datas.append(
        (
            str(
                BACKEND
                / "modules"
                / "llm"
                / "capability"
                / "measured"
                / "capabilities.json"
            ),
            "modules/llm/capability/measured",
        )
    )

    for package in (
        "onnxruntime",
        "docling",
        "docling_core",
        "docling_ibm_models",
        "docling_parse",
        "rapidocr",
        # Studio document formats: the model writes python-docx/pptx/xlsxwriter/
        # reportlab code (worker/studio/office/) that the worker runs, so none are
        # imported statically anymore — the analyser cannot see them, and each also
        # reaches package data by path (Office templates, reportlab core fonts).
        "docx",
        "pptx",
        "xlsxwriter",
        "reportlab",
        # Document scripts may write Excel with it, and the workbook summary reads
        # every script's workbook with it (worker/studio/script_document/).
        "openpyxl",
    ):
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden

    # torchvision loads native extensions dynamically, so a source install works
    # while the frozen worker fails only when its first PDF initializes the
    # layout model. Its sources stay out: it ships as bytecode (torch_bytecode_only.py).
    tv_datas, tv_binaries, tv_hidden = collect_all(
        "torchvision", include_py_files=False
    )
    datas += tv_datas
    binaries += tv_binaries
    hiddenimports += tv_hidden

    # Transformers exposes AutoImageProcessor through lazy imports, invisible to
    # the analyser; only the model families Docling's layout engine loads ship.
    for family in TRANSFORMERS_MODELS_USED:
        hiddenimports += collect_submodules(f"transformers.models.{family}")
    hiddenimports += [
        "transformers.image_processing_utils",
        "transformers.image_processing_utils_fast",
    ]
    datas += copy_metadata("transformers")

    binaries += collect_dynamic_libs("tokenizers")

    # Every prompt a case ships, plus office's per-format SKILL.md: all read through
    # importlib.resources, so the analyser does not see them as source.
    datas += collect_data_files("worker.studio", includes=["**/*.md"])
    # Studio's Web page prompt carries the agent's design guide whole (ADR 0066).
    datas += collect_data_files(
        "modules.agent", includes=["skills/surfsense-html/design.md"]
    )
    datas += collect_data_files("modules.chat", includes=["prompts/*.md"])

    # lameenc, which encodes a podcast as MP3, is found by its import. Its
    # dist-info holds lameenc's LGPL-3.0 and ships only when named; the GPL-3.0 that
    # LGPL-3 §4(b) also asks for, LAME's licence and notice, and where both sources
    # are, ship from bundling/licenses/lameenc beside the module.
    datas += copy_metadata("lameenc")
    datas.append(
        (str(BACKEND / "bundling" / "licenses" / "lameenc"), "lameenc-licenses")
    )

    # The decode child (--decode-audio) reads recordings with miniaudio, whose
    # compiled half is a cffi extension: the C code imports _cffi_backend, which
    # the analyser cannot see. Its metadata carries the MIT notice, which asks to
    # travel with every copy.
    hiddenimports += ["miniaudio", "_miniaudio", "_cffi_backend"]
    datas += copy_metadata("miniaudio")

    # Huey resolves a task by its name, so the module that registers it must be in.
    hiddenimports += [
        "modules.documents.tasks",
        "modules.artifacts.tasks",
        "modules.agent.data_analysis.task",
        "modules.documents.web_sources.background_pull.pull_task",
        "modules.plugins.bundles.tasks",
    ]

    # The plugins worker pulls a link added from the web through one of SurfSense's
    # plugins, found in this list. The list refuses an entry whose icon is not beside it.
    datas.append(
        (
            str(
                BACKEND
                / "modules"
                / "plugins"
                / "lists"
                / "first_party"
                / "plugins.json"
            ),
            "modules/plugins/lists/first_party",
        )
    )
    datas.append(
        (
            str(BACKEND / "modules" / "plugins" / "lists" / "first_party" / "icons"),
            "modules/plugins/lists/first_party/icons",
        )
    )

    # Document scripts (worker/document_script/) draw charts, and nothing imports
    # matplotlib statically. Naming pyplot runs PyInstaller's own hooks, which add
    # mpl-data and the backend chosen in the spec. savefig to .pdf or .svg, and
    # PdfPages, import their canvas by name, which the hooks do not follow.
    hiddenimports += [
        "matplotlib.pyplot",
        "matplotlib.backends.backend_pdf",
        "matplotlib.backends.backend_svg",
        # Analysis scripts read spreadsheets with it (modules/agent/data_analysis);
        # only Docling reaches it statically, so it is named in case that changes.
        "pandas",
    ]

    # Apple's Vision (worker/ingestion/scan_ocr/vision.py) is imported inside
    # functions, which the analyser follows; named so a refactor cannot drop it
    # unseen. `--check-scan-ocr` checks the frozen worker on every release.
    if sys.platform == "darwin":
        # Not collect_all("objc"): it would ship pyobjc-core's 23 MB of .dSYM bundles
        # and test extensions into a notarised app.
        hiddenimports += ["objc", "Foundation", "Quartz", "Vision"]
    return datas, binaries, hiddenimports
