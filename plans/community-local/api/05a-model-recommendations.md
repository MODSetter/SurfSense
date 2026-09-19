# API — Phase 5: Hardware-aware model recommendations

> **The runtime and manifest halves are superseded by Phase 7.**
> [`07-llamacpp-runtime.md`](07-llamacpp-runtime.md) replaces Ollama with
> `llama-server`, moves llmfit out of the app, and takes the manifest to
> `schema_version` **3** with a `variants` list. The `schema_version: 2` shape
> below describes what ships **today**, not what phase 7 writes. The catalog
> boundary, the normalized shapes and the frontend contract still govern.
>
> Owns: `backend/modules/llm/recommendations/`, the llmfit adapter, the
> runtime-install boundary, and the normalized catalog API. Packaging:
> [`05c-packaging.md`](05c-packaging.md). Frontend:
> [`../frontend/05-install-ux.md`](../frontend/05-install-ux.md). Remote
> connections: [`05b-openai-compatible-connections.md`](05b-openai-compatible-connections.md).

## Goal

Show generation models the current computer can run, put exact configurations
tested by SurfSense first, and install the selected configuration with one
action. llmfit supplies catalog metadata, hardware detection, and fit estimates;
SurfSense owns support policy, artifact trust, installation, and inference.

This phase does not change the bundled bge-small embedding model, its
384-dimensional index, ingestion, retrieval, or chat SSE.

## Boundaries

```text
llmfit catalog + hardware fit
             │
             ▼
      LlmfitAdvisor adapter
             │ normalized ScoredModel[]
             ▼
     CatalogService + curated models JSON
             │
             ▼
    runtime artifact resolution
       ├── Ollama (v1)
       └── llama.cpp (future)
             │
             ▼
        Curated + Explore API
```

- **llmfit** answers which generation configurations fit this hardware. It is
  not an inference runtime and is never forked or modified by SurfSense.
- **Curated models** name exact team-tested configurations. Family membership
  alone never grants support.
- **Runtime adapters** answer whether a scored model has an artifact SurfSense
  can install, then own download, storage, process lifecycle, and inference.
- **The frontend** renders the normalized SurfSense contract. It never parses
  llmfit output or chooses an artifact URL.

## llmfit integration contract

Ship a pinned official llmfit binary and invoke it as a short-lived subprocess.
Do not add a permanent `llmfit serve` sidecar for a scan performed once per API
process. Keep the adapter boundary so it can move to llmfit's REST API later
without changing the domain service or frontend.

Commands:

```bash
llmfit --json system
llmfit --max-context 8192 --json fit
```

As built there is **no `-n` result cap** — the scan takes llmfit's whole
compatible set, which is what "without a result count limit" under Catalog
assembly asks for. `_fit()` appends `--providers <name>` when a provider filter
is passed, which is how the curated manifest's `advisor_providers` narrows a
targeted scan.

The adapter accepts only the fields SurfSense uses:

- `name` — canonical model id;
- `fit_level` and `score`;
- `runtime`, `run_mode`, and `best_quant`;
- `memory_required_gb`, `memory_available_gb`, and `utilization_pct`;
- `disk_size_gb`, `estimated_tps`, `prefill_tps`, and `ttft_ms`;
- `estimate_confidence` and `estimate_basis`;
- `effective_context_length`;
- `capability_ids` and `license`;
- `ollama_name` and `gguf_sources`.

llmfit's CLI currently overloads some machine-code fields with human labels
while its REST API returns lowercase machine codes plus `*_label`. Normalize
both forms at the adapter seam (`"Good"` and `"good"` become `good`) and retain
unknown notes instead of failing the whole catalog. Pin the binary version and
keep representative JSON fixtures so an upgrade that changes this contract
fails tests.

`provider` in llmfit output means the model publisher, not the SurfSense
inference provider. Name it `publisher` in SurfSense DTOs. `runtime` is an
llmfit execution estimate, not proof that SurfSense has an installer.

Cache the successful system profile and scored catalog for the API process.
A manual refresh invalidates both and performs one new scan. Concurrent callers
share one in-flight scan.

**Built one layer deeper than that.** The cache is on disk, at
`{data_dir}/llmfit-scan.json`, written atomically through a `.tmp` rename and
invalidated when either its `cache_version` or the recorded `llmfit_version`
stops matching — so a scan survives an app restart, not just the process. The
in-memory copy and its lock sit in front of it. The consequence that matters:
**`scan()` never spawns llmfit unless `refresh=True`.** Loading the catalog
page costs no hardware probe; only the explicit "Scan hardware" action does.

## Domain contracts

```python
class ModelAdvisor(Protocol):
    async def scan(self, max_context: int) -> AdvisorCatalog: ...


class LocalRuntime(Generator, Protocol):
    async def resolve(self, model: ScoredModel) -> InstallPlan | None: ...
    async def installed_models(self) -> list[InstalledModel]: ...
    def install(self, plan: InstallPlan) -> AsyncIterator[DownloadProgress]: ...
```

`Generator` remains the chat seam used by `modules/chat`. OpenAI-compatible
remote connections do not implement `LocalRuntime`: they expose already-served
models and cannot install or delete them. Do not add llmfit to the provider
registry: it advises; it never answers a chat request.

The normalized `ScoredModel` carries a canonical id and fit metadata only.
`InstallPlan` carries the selected runtime, runtime-specific model id, expected
bytes, quantization, and trusted artifact identity. The plan is constructed on
the server and is never accepted from the renderer.

### Ollama runtime, first implementation

- Resolve only llmfit rows with a non-empty, known-good `ollama_name`.
- Reuse the existing `/api/tags`, `/api/show`, `/api/pull`, and `/api/chat`
  integration.
- Score the artifact SurfSense will actually pull. If an Ollama tag does not
  pin llmfit's `best_quant`, do not claim that quantization was installed.
- The packaged private Ollama remains authoritative for installed state and
  model storage; llmfit's own installed flag is informational only.

### llama.cpp, later

> **Now.** [`07-llamacpp-runtime.md`](07-llamacpp-runtime.md) is this section,
> specified. It goes further than "adding a runtime": llama.cpp becomes the
> *only* local runtime, llmfit leaves the installer for CI, and the Explore
> bucket becomes a Hugging Face search over every GGUF rather than the subset
> llmfit happens to know.

A future adapter resolves a canonical model and quantization to a verified GGUF,
downloads atomically, starts `llama-server`, and implements the existing
`Generator` stream. Adding it changes the runtime registry and packaging, not
  the llmfit adapter, curated-model policy, catalog service, or frontend response shape.

## Curated models manifest

Package:

```text
backend/modules/llm/recommendations/curated-models.json
```

Shape:

```json
{
  "schema_version": 2,
  "advisor_providers": ["Alibaba"],
  "models": [
    {
      "model_id": "Qwen/Qwen3-8B",
      "family": "Qwen3",
      "minimum_fit": "good",
      "minimum_context": 8192,
      "allowed_quantizations": ["Q4_K_M"],
      "artifacts": {
        "ollama": {
          "name": "qwen3:8b",
          "quantization": "Q4_K_M"
        }
      },
      "label": "Qwen3 8B",
      "parameter_count": "8B",
      "size_bytes": 5225374496
    }
  ]
}
```

`schema_version` is **2**. Version 2 added the three display fields — `label`,
`parameter_count`, `size_bytes` — so a curated row can render before any
hardware scan has produced an estimate for it, and `advisor_providers` at the
top level to scope a targeted scan. The shipped manifest carries eight Qwen
entries.

Entries are exact model configurations, even though the frontend groups them by
`family`. Prefer an immutable runtime artifact or digest when the runtime
supports one; a mutable family name is not a verification boundary. The
manifest contains no hardware score and is not copied into SQLite.

## Catalog assembly

SurfSense requests llmfit's complete compatible model set without a result
count limit. For each llmfit generation model:

1. Normalize its identity and score.
2. Exclude embedding-only entries.
3. Ask each enabled local runtime to resolve an install plan.
4. Drop uninstalled entries with no resolvable trusted artifact.
5. Overlay the curated-model manifest.
6. Apply SurfSense's real context target and reserve memory for the OS,
   Electron, API, worker, parser, and fixed embedding model.
7. Enforce one catalog row per exact `(runtime, runtime_model)` target. An
   explicit curated mapping wins over an external mapping. When external names
   collide, show one row named with the exact runtime target and use the most
   conservative colliding hardware estimate instead of guessing a catalog
   identity. Record collisions once per scan in developer logs; they are not a
   user-actionable recommendation warning.
8. Partition and rank:
   - **Curated** (called *Recommended* when this was written, renamed in the
     code): every exact manifest entry;
   - **Explore:** remaining installable `perfect`, `good`, or `marginal`
     entries;
   - **Installed:** always visible, including a warning when marginal or too
     tight.

Ranking is deterministic: fit class, llmfit score, then canonical id. Curated
rows are excluded from Explore, so nothing appears twice.

**Two rules here were built the other way round, deliberately.**

*A curated model that does not fit stays curated.* This spec had it move to
Explore with its fit warning. The code keeps it in its own section at whatever
fit the scan found, on the reasoning that a poor fit is better shown as an
honest badge than hidden among thousands of Explore rows — and that acting on
one is already gated by the marginal/too-tight install confirmation. The promise
this section was protecting still holds: team-tested is not a claim about every
computer, it is just made in the badge instead of in the bucket.

*Neither Curated nor Installed needs a scan.* Steps 1-8 read as a pipeline that
begins with llmfit output, which would leave a fresh install looking at an empty
page until it ran a hardware probe. As built, Curated is populated straight from
the manifest — the display fields added in `schema_version` 2 are exactly what
makes a row renderable with no estimate — and Installed from the runtime's own
inventory. A manifest row that no scan has matched is still installable, because
resolving it needs only the `ollama_name` the manifest already pins, so a real
install plan is registered against the placeholder and `/install` behaves
identically. Rows with no estimate carry `fit: unknown` and null resource
fields, and the frontend suppresses the badge entirely until a scan has
happened rather than showing "unknown" to someone who never asked. Only Explore
and the fit badges require step 1.

## HTTP contract

### `GET /llm/system`

Returns the normalized hardware profile, scan warnings, llmfit version, and
whether estimates are available.

### `GET /llm/catalog`

Returns:

```json
{
  "hardware": {},
  "curated": [],
  "explore": [],
  "installed": [],
  "warnings": [],
  "scanned": false,
  "llmfit_version": null,
  "runtime_status": {}
}
```

The bucket is `curated`, not `recommended`. `scanned` tells the frontend whether
a hardware scan stands behind these rows, which is what lets it render curated
and installed models immediately and offer "Scan hardware" in place of Explore.

Each catalog row includes an opaque `catalog_id`, canonical model id, family,
display label, fit, resource estimates, license, installed/selected state,
the chosen runtime name, and a server-derived `can_delete` capability. It does
not expose artifact URLs or local paths.
`?refresh=true` invalidates the cached hardware/catalog scan.

### `POST /llm/install`

Body:

```json
{"catalog_id": "<opaque id>", "select": true}
```

The API re-runs server-side resolution against the current catalog, checks disk
space, and streams the existing newline-delimited progress shape. It rejects a
stale, unknown, unresolvable, or untrusted id before streaming. On success,
`select=true` updates `SelectedModel(GENERATION)` to the installed runtime id.
Partial artifacts never become selectable.

Keep `GET /llm/providers`, local provider inventory, and
`GET/PUT /llm/selection/generation`. Remote inventory belongs to
`GET /llm/connections/{id}/models`; see the connection spec. The
provider-specific pull route may remain during migration, but the final
frontend calls the normalized install route.

### `GET /llm/onboarding`

Returns whether the user has completed model onboarding.

### `POST /llm/onboarding`

Writes the durable completion marker. Requires a persisted generation
selection. Image is optional. Selecting or clearing a model never writes or
resets this marker. Settings Use actions must not call this route.

### `DELETE /llm/providers/{provider}/models/{model_name}`

Deletes an installed local generation model through the runtime API. For
Ollama, the adapter calls `DELETE /api/delete` with the exact model name and
tag. The endpoint rejects remote providers, embedding-only models, active
downloads, active chat streams, and deletion while the separate Studio worker
is generating. If the deleted model is
selected, the same transaction clears `SelectedModel` and reports
`selection_cleared: true`.

## Prompt tiers

Not in the original spec, and now depended on by chat and by every Studio
format: a selected model is **fingerprinted at selection time**, and its
fingerprint decides which of three prompts it is given.

`modules/llm/profile/` owns the classification. A `Fingerprint` carries
`provider`, `name`, and three nullable facts — `params_b`, `vendor`, and `line`
(`flagship` or `small`) — collected from Ollama's `/api/tags` and `/api/show`,
from a remote connection's `/models`, or, failing both, from heuristics on the
name. `classify()` turns it into a `Tier`:

| Known | Tier |
|---|---|
| `params_b` < 7.0 | `compact` |
| `params_b` < 100.0 | `capable` |
| `params_b` ≥ 100.0 | `frontier` |
| no count, but a `vendor` | `frontier` |
| no count, `line` is flagship / small | `frontier` / `capable` |
| nothing, provider is Ollama | `compact` |
| nothing, remote | `capable` |

The thresholds encode a claim about scaffolding, not about quality: below the
first a model loses accuracy when asked to follow a structure, between the two
it gains from one, and above the second it writes better from judgement than
from steps. The last two rows are the same bet — a hosted endpoint runs models
too big for a laptop, Ollama runs the laptop.

Revision `0010` adds `params_b`, `vendor` and `line` to `selected_models`. **The
tier itself is not stored**: `SelectedModel.tier` calls `classify()` on read, so
retuning a threshold changes behaviour without a migration or a re-selection.

`modules/llm/prompting/` is the other half. `load(package, tier, case=None,
**slots)` reads `{package}/prompts/{tier}.md`, or `{package}/prompts/{case}/{tier}.md`
when a package has more than one prompt, and fills `$slot` placeholders through
`string.Template`; `focus()` appends the user's steer as one line. Every prompt
therefore lives as markdown beside the code that uses it — eleven cases at three
tiers, so 33 files: chat, the four `content/` formats, `office/`, `web/html/`,
the two `media/visual/` formats, and podcast outline and draft separately. A
unit test asserts every case ships all three. No `import` statement names any of
them, so the PyInstaller specs collect them by path, split along what each binary
runs: `api.spec` takes only `modules.chat`'s three, and `worker.spec` takes those
plus every `*.md` under `worker.studio`.

## Failure behavior

- llmfit missing, timed out, or malformed: return installed runtime models and
  a recommendation warning; do not prevent app startup or chat with an already
  selected model.
- Incomplete hardware detection: return the profile plus warnings and avoid a
  false `perfect` claim.
- Runtime unavailable: keep catalog information visible and disable installs
  for that runtime.
- No trusted runtime artifact: omit Download; never pass through a guessed URL.
- Insufficient disk: reject before download with required and available bytes.
- Cancelled/interrupted pull: clean temporary state where the runtime permits
  it and never auto-select the incomplete model.
- Deletion never edits runtime storage directly and never silently selects a
  replacement model.

## Tests

- Adapter fixtures cover system JSON, fit JSON, labels versus machine codes,
  nullable estimates, unknown fields, timeout, nonzero exit, and malformed JSON.
- Catalog policy covers Curated/Explore partitioning, family grouping metadata,
  deterministic ranking, deduplication, memory reserve, and installed models
  that no longer fit. Also: a catalog served with no scan at all, curated
  placeholders staying installable, and the scan cache surviving a restart.
- Runtime resolution covers valid/absent Ollama mappings and prevents an
  arbitrary renderer-supplied tag or URL.
- Integration covers catalog → install progress → installed inventory →
  selection, with fake llmfit output and a stub runtime.
- Deletion coverage includes exact Ollama payloads, remote/capability rejection,
  active-operation conflicts, and selected-model cleanup.
- Packaging smoke runs `llmfit --json system` on each clean target OS.

## Acceptance

- A clean supported machine sees Curated models followed by Explore, with Curated
  present before any hardware scan has run.
- Every enabled Download action resolves to a runtime artifact SurfSense can
  install.
- One Download & Use action installs and selects a model.
- llmfit being unavailable degrades recommendations without breaking installed
  model selection or chat.
- Adding a fake llama.cpp runtime in tests requires no change to llmfit parsing,
  Curated partitioning, or the frontend catalog schema.
