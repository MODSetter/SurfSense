"""What the API role carries that PyInstaller's analyser cannot follow.

Chat retrieval embeds the query, so the encoder (onnxruntime, tokenizers) ships.
"""

from common import BACKEND, database_inputs
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# What an API-only freeze leaves out. Only the listing of modules the API role
# may import is analysed with these (api_absent_modules.py); the shipped bundle
# carries them for the worker. 260 MB the analyser cannot tell are optional:
# chonkie names transformers only under TYPE_CHECKING and imports pandas inside
# TableChef, and those two then reach opencv and scipy. Chunking here is
# RecursiveChunker over the Rust tokenizer, which touches none of them.
# onnxruntime's model-conversion tooling arrives the same way via collect_all;
# retrieval only builds an InferenceSession, which lives in onnxruntime.capi.
API_ONLY_EXCLUDES = [
    "docling",
    "torch",
    "torchvision",
    "cv2",
    "pandas",
    "scipy",
    "transformers",
    # Only the worker encodes a podcast; the API's voice check keeps its WAV.
    "lameenc",
]


def api_inputs() -> tuple[list, list, list]:
    """(datas, binaries, hiddenimports) the API role needs in the bundle."""
    datas, binaries, hiddenimports = database_inputs()
    # Read by path, so the analyser cannot see it. Without it a frozen build has no
    # curated list, and the model screen is empty on the machine that most needs it.
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
    # Read by path, so the analyser cannot see it. Without this every remote model
    # reads as unknown in a frozen build only.
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
    # Read by path, so the analyser cannot see it. Without it every model reads as
    # not measured in a frozen build only, and no model gets the agent.
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
    # Read by path, so the analyser cannot see it. Without it a frozen build lists
    # none of SurfSense's own plugins.
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
    # Read by path too, and checked beside the list: without them a frozen build
    # lists none of SurfSense's plugins either.
    datas.append(
        (
            str(BACKEND / "modules" / "plugins" / "lists" / "first_party" / "icons"),
            "modules/plugins/lists/first_party/icons",
        )
    )

    # shared/app_version.py reads the release version from the package's metadata,
    # which a frozen build has only if copied. Without it no registry entry with a
    # minimum app version is listed.
    datas += copy_metadata("surfsense-local-backend")

    # Chat's three prompts are read through importlib.resources, not imported.
    datas += collect_data_files("modules.chat", includes=["prompts/*.md"])
    # So is the agent's, which the API writes into opencode's configuration, and
    # its skills folder, which that configuration points opencode at by path: each
    # skill's files beside its SKILL.md too, its examples included.
    datas += collect_data_files(
        "modules.agent", includes=["prompts/*.md", "skills/**/*.md"]
    )

    # uvicorn loads its loop, protocol, and lifespan implementations by string.
    hiddenimports += collect_submodules("uvicorn")

    # The query encoder. onnxruntime's native libs load from C, not an import.
    onnx_datas, onnx_binaries, onnx_hidden = collect_all("onnxruntime")
    datas += onnx_datas
    binaries += onnx_binaries + collect_dynamic_libs("tokenizers")
    hiddenimports += onnx_hidden
    return datas, binaries, hiddenimports
