# API — Phase 5: Packaging

> **Phase 7 supersedes the generation-runtime half.**
> [`07-llamacpp-runtime.md`](07-llamacpp-runtime.md) replaces the bundled Ollama
> with `llama-server` and **stops shipping llmfit entirely**. The llmfit and
> first-run-download sections below are rewritten to match; the PyInstaller,
> sqlite-vec, Alembic and model-pack sections are unaffected and still govern.

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
- A pinned `llama-server` build plus the versioned curated-model manifest;
  catalog and install routes are specified in
  [`07-llamacpp-runtime.md`](07-llamacpp-runtime.md) (which supersedes the
  route table in [`05a-model-recommendations.md`](05a-model-recommendations.md)).

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

## Generation recommendations and models — advisor bundled, weights downloaded

The chat model is the one heavy file (1.4GB+), and bundling it would double the
installer for something the app does not need to *start*. So it is not shipped.
The installer carries only what runs offline — code, Docling/OCR weights, the
bge embedder, the pinned `llama-server` build, and `curated-models.json` — and
ingestion and search work the moment the app opens. **llmfit is not shipped**
(see below), which removes 27 MB from every target.

### llmfit is not packaged

**Superseded by phase 7.** llmfit ran on the user's machine to detect hardware
and score models. Both jobs moved:

- **Hardware** now comes from `ggml_backend_dev_memory()` in the shipped ggml
  libraries, via `ctypes` — the allocator's own view, ~180 ms, no subprocess.
- **Scoring** happens on a maintainer's machine, a few times a year, and the
  numbers are committed into `curated-models.json` as source.

So there is no `resources/llmfit/`, no `SURFSENSE_LOCAL_LLMFIT_PATH`, no
subprocess to time out, no checksum to stage, and nothing for code signing or
antivirus smoke tests to cover. `llmfit --json system` is not run from a packaged
path because the binary is not in the package.

The rule that replaced it: **anything that returns the same answer on every
machine is computed once and shipped as data; anything that differs per machine
is measured on that machine by the runtime that will do the work.**

### llama-server executable

- Pin one llama.cpp build number **and its SHA-256** in `fetch-llamacpp.mjs`;
  never fetch a floating tag. llama.cpp publishes ~10 builds a day with no
  stable channel, so the pin matters more here than it did for Ollama —
  `fetch-ollama.mjs` verified no checksum at all.
- Stage one archive per target under `resources/llamacpp/`, retaining upstream
  licence and notices. Prune to `llama-server` plus the libraries it links: the
  macOS tarball ships 24 executables and only one is needed, which also shrinks
  the notarization surface.
- Sizes and per-OS details, including CUDA inside the Windows installer, are in
  [`07-llamacpp-runtime.md`](07-llamacpp-runtime.md) under **Packaging, three
  targets**.
- Code signing, notarization and antivirus smoke tests cover `llama-server` and
  its libraries. Note it spawns **child processes** in router mode, so the
  hardened runtime needs testing against a grandchild, not just the sidecar.
- CI runs `llama-server --list-devices` from the final packaged resource path on
  each clean target.

Model licences are not permission to redistribute weights. SurfSense ships no
generation weights; the app downloads the file its manifest pins, or one the
user finds by search.

### First-run model download

The generation model arrives in first-run setup with progress through the
normalized catalog boundary
([`05a-model-recommendations.md`](05a-model-recommendations.md)):

- `GET /llm/system` — the hardware budget, from the runtime's allocator. No
  scan, no status flag, no button.
- `GET /llm/catalog` — curated plus installed, every row badged. **No network.**
- `GET /llm/search` — the Hugging Face tier, paged and egress-gated. Separate
  route so the page never blocks on it.
- `POST /llm/install` — fetches the pinned file server-side, streams progress,
  and optionally selects it.
- `GET/PUT /llm/selection/generation` — reads or validates the selection.

A fully offline machine keeps chat through **Add a .gguf file** on the same
screen. With search unavailable, that and the packaged manifest are the only two
routes to a model, so it is a first-class control rather than an advanced
option. Import validates the GGUF header, rejects an unsupported architecture,
and links the file into the models directory; the renderer never provides an
arbitrary download URL.

## Acceptance

- Clean VM Path B: install → wizard → upload → chat.
- The catalog renders with a hardware line and badged rows on first paint, with
  no network call and no binary beyond `llama-server`.
- Tampering with the staged llama.cpp archive fails checksum verification.
- `llama-server --list-devices` succeeds from the packaged resource path on each
  target.
- Download & Use fetches the pinned GGUF, completes, and selects the exact
  installed model; no generation weights are present before that action.
- With networking disabled: curated rows badge correctly and a `.gguf` imported
  from disk reaches chat.
- Quit → no orphan `surfsense-*` or `llama-server` processes, including the
  model workers the router spawns.
