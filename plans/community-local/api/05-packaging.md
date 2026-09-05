# API — Phase 5: Packaging

## Goal

Installers for Paths A / B / C.

## Work

- PyInstaller specs: `surfsense-api` + `surfsense-worker` (`--onedir`; worker hiddenimports from [`../worker/05-packaging.md`](../worker/05-packaging.md)).
- **`collect_dynamic_libs('sqlite_vec')`** in both specs — see below.
- `alembic/versions/` as spec data; the packaged app runs migrations on launch.
- electron-builder `extraResources` → `resources/backend/`.
- CI: win/mac/linux; smoke `/health`.
- Models outside exe — shipped as `extraResources`, `SURFSENSE_LOCAL_MODELS_DIR`
  pointed at them; `scripts/fetch_embedding_model.py` fetches the same files for CI.
- Manifest or routes for model pack URLs (frontend download UI).

## Files no import statement names

PyInstaller decides what to bundle by following `import` statements through the
bytecode. Anything reached by a path at runtime is invisible to it, and the app
that works from source starts failing only once it is frozen — on a clean
machine, per OS, at the end of the project.

| File | Reached by | Symptom if dropped |
|---|---|---|
| `sqlite_vec/vec0.so` | `conn.load_extension(path)` from C | **App will not start.** Every connection loads the extension, so the migration on launch is the first thing to die |
| `alembic/versions/*.py` | Alembic reads the directory | No revisions found; an empty database stays empty |
| `onnxruntime` native libs | loaded by the C extension, not an import | Every embed raises; no document reaches `ready` |
| bge-small ONNX + tokenizer | read by path from `models_dir` | Same: ingest cannot embed |
| Docling parser models | downloaded or bundled data | Every ingest of a PDF fails |

## Proven: the frozen binary opens its database

An opt-in guard,
[`tests/packaging/test_frozen_boot.py`](../../../surfsense_local/backend/tests/packaging/test_frozen_boot.py)
(`pytest -m packaging`, off by default since it builds a binary), freezes a
minimal entry and runs it: the frozen binary migrates a real database from
bundled `versions/`, loads `vec0.so`, and round-trips a vector through
`chunk_vectors` — on no source tree, `sys.frozen` true. A source-run test cannot
catch a dropped `.so` or `versions/`; only a frozen one can. So a `sqlite-vec` /
`alembic` / `pyinstaller` bump that breaks the freeze fails a test instead of a
user's first launch. The flags it proves, to carry into the real specs:

- **`--collect-all sqlite_vec`** — lands `vec0.so` under `_internal/sqlite_vec/`,
  where `sqlite_vec.load()` finds it by the package's own path with no code
  change.
- **`--add-data alembic:alembic`** — ships the version scripts at the relative
  path the app resolves (`migrations.py` walks up from its own `__file__`, which
  PyInstaller sets correctly). `env.py` is data, not analyzed, so its imports
  need naming as **hidden imports**: `alembic.context`,
  `alembic.runtime.migration`, `alembic.runtime.environment`.
- **`--paths <backend>`** so `import shared.*` resolves during analysis.

Left for this phase: the real API spec adds `collect_submodules("uvicorn")` for
the server it actually runs; the worker spec adds its heavy hidden imports
([`../worker/05-packaging.md`](../worker/05-packaging.md)); then the Electron
`extraResources` wiring and the per-OS clean-VM run. (One gotcha for those specs:
a top-level dir named `packaging/` shadows the `packaging` PyPI package — name it
anything else.)

## The model packs

Two, both outside the exe:

- **Embedding, ~66MB.** bge-small int8 ONNX, its tokenizer and config. Small
  enough to ship in every installer; `scripts/fetch_embedding_model.py` places the same
  files for development and CI.
- **Parser, ~1.6GB.** Measured on a first real conversion, not estimated:
  Docling downloads the layout and OCR weights into `~/.cache/huggingface`, and
  RapidOCR writes into `site-packages` — read-only inside a frozen bundle, so
  that download fails rather than being merely slow. First run took 2m50s. Ship
  it as `extraResources` or fetch it once in the install wizard.

Both live under `models_dir`. `parsing.py` already sets `HF_HOME` there before
Docling loads, so nothing writes inside the bundle; packaging sets
`SURFSENSE_LOCAL_MODELS_DIR` to the shipped location. torch is already pinned to
the CPU wheels ([`../worker/02-ingest.md`](../worker/02-ingest.md)); the CUDA
build would have added 3GB to every installer.

## The generation model — downloaded, not bundled

The chat model is the one heavy file (1.4GB+), and bundling it would double the
installer for something the app does not need to *start*. So it is not shipped.
The installer carries only what runs offline — code, Docling/OCR weights, the
bge embedder, the Ollama binary — and ingestion and search work the moment the
app opens.

The model arrives in first-run setup, in the UI, with progress, over the
provider layer already built ([`03-chat.md`](./03-chat.md)):

- `GET /llm/{provider}/catalog` — the choices with their download sizes, a lite
  Qwen as the pre-selected default. A default *selection*, not a shipped file.
- `POST /llm/{provider}/pull` — streams download progress to a bar.
- `POST /llm/selection` — records the choice in `selected_models`.

A fully offline machine keeps chat through an "import a local model" option on
the same screen (a file, or a model already in Ollama), so airgapped is an opt-in
path rather than a cost every installer pays. Packaging adds no backend here.

## Acceptance

- Clean VM Path B: install → wizard → upload → chat.
- Quit → no orphan `surfsense-*` processes.
