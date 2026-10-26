"""The frozen backend's one entry: Electron starts it as `api` or `worker <queue>`.

Both roles share one PyInstaller bundle so their libraries ship once
(bundling/backend.spec). The flags the app re-runs this binary with keep their
shapes from the two binaries this replaced, so no caller changes.
"""

import sys
from pathlib import Path

_USAGE = "usage: surfsense-backend api | worker <ingest|studio|plugins>"

# Absent from the API role exactly as from the API-only binary this replaced,
# written by bundling/api_absent_modules.py. An API that finds torch beside it
# would load it, and an optional import would quietly change behaviour.
API_ABSENT_MODULES = "api_absent_modules.txt"

_API_FLAGS = {"--check-retrieval-runtime", "--probe-devices"}
_WORKER_FLAGS = {
    "--check-vision-runtime",
    "--check-scan-ocr",
    "--check-docling-reading",
    "--run-document-script",
    "--decode-audio",
}


def hide_worker_only_modules(listing: Path) -> list[str]:
    """Make each listed module unimportable here, as if it were not shipped.

    A None entry in sys.modules makes `import` raise ModuleNotFoundError and
    importlib.util.find_spec return None, which is what an absent module does.
    """
    hidden = [name for name in listing.read_text().split() if name not in sys.modules]
    for name in hidden:
        sys.modules[name] = None  # type: ignore[assignment]
    return hidden


def _api(arguments: list[str]) -> None:
    hide_worker_only_modules(Path(sys._MEIPASS) / API_ABSENT_MODULES)  # type: ignore[attr-defined]
    import main

    if arguments == ["--check-retrieval-runtime"]:
        main.check_retrieval_runtime()
        _check_api_role_is_light()
    else:
        main.run(arguments)


def _check_api_role_is_light() -> None:
    """The API process must not reach the worker's parsing stack."""
    import importlib.util

    reachable = [
        name
        for name in ("torch", "transformers", "docling", "cv2", "pandas", "scipy")
        if importlib.util.find_spec(name) is not None
    ]
    if reachable:
        sys.exit(f"the API role can import worker-only modules: {reachable}")
    sys.stdout.write("api role imports no worker-only modules\n")


def _worker(arguments: list[str]) -> None:
    import warnings

    # torch ships as bytecode only (bundling/torch_bytecode_only.py), and its
    # overload registry says so once per function at import.
    warnings.filterwarnings(
        "ignore", message="Unable to retrieve source for @torch.jit._overload"
    )
    from worker.command_line import run

    run(arguments)


def dispatch(arguments: list[str]) -> None:
    """Start the role, or the self-run mode, the arguments name."""
    flag = arguments[0] if arguments else ""
    if arguments == ["api"]:
        _api([])
    elif flag == "worker" and len(arguments) == 2:
        _worker(arguments[1:])
    elif flag in _API_FLAGS:
        _api(arguments)
    elif flag in _WORKER_FLAGS:
        _worker(arguments)
    else:
        # Never a default role: a stray launch must not start a server that
        # nothing is waiting on and nothing will stop.
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)


if __name__ == "__main__":
    import multiprocessing

    # First: a multiprocessing child arrives with its own arguments, which
    # are not a role.
    multiprocessing.freeze_support()
    dispatch(sys.argv[1:])
