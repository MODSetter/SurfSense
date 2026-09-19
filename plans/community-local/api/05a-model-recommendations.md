# API — Phase 5: Model selection and prompt tiers

> **The recommendation half of this phase is gone.** llmfit-in-the-app, the
> Ollama runtime adapter, the Curated/Explore partitioning and the catalog HTTP
> surface were all replaced by
> [`07-llamacpp-runtime.md`](07-llamacpp-runtime.md). What remains here still
> governs and is not superseded: **prompt tiers**, **model fingerprinting at
> selection time**, and **onboarding**. See **What moved to Phase 7** for the
> mapping, so nothing is lost by deletion.
>
> Owns: `modules/llm/profile/`, `modules/llm/prompting/`, the `selected_models`
> fingerprint columns, and the onboarding marker. Remote connections:
> [`05b-openai-compatible-connections.md`](05b-openai-compatible-connections.md).
> Packaging: [`05c-packaging.md`](05c-packaging.md). Frontend:
> [`../frontend/05-install-ux.md`](../frontend/05-install-ux.md).

## Goal

Decide, once, at the moment a model is selected, **how that model should be
prompted** — and keep that decision durable, cheap to re-tune, and independent of
which runtime serves the model.

This phase does not choose models, score hardware, install anything, or render a
catalog. Phase 7 owns all of that.

It does not change the bundled bge-small embedding model, its 384-dimensional
index, ingestion, retrieval, or chat SSE.

## What moved to Phase 7

Kept as a map rather than deleted silently, because the code implementing the
left column still exists until 7.6 removes it.

| Was specified here | Now |
|---|---|
| llmfit as a packaged subprocess (`--json system`, `--json fit`) | **Not shipped.** Authoring-time only, on a maintainer's machine — [`07`](07-llamacpp-runtime.md) **Decisions**, and [`05c-packaging.md`](05c-packaging.md) |
| `LlmfitAdvisor`, the `ModelAdvisor` protocol, `AdvisorCatalog` | Deleted. Hardware comes from `ggml_backend_dev_memory()`, fit from the GGUF header — [`07`](07-llamacpp-runtime.md) 7.1–7.2 |
| `{data_dir}/llmfit-scan.json`, `CACHE_VERSION`, the `scanned` flag | Deleted. There is no scan and no scan button |
| Ollama runtime adapter, `ollama_name` resolution, `/api/pull` | `llama-server` router mode — [`07`](07-llamacpp-runtime.md) **Runtime contract**, 7.3 |
| Curated / Explore / Installed partitioning, the five-way `fit_level` | Two tiers (curated manifest, Hugging Face search) and three fit states — [`07`](07-llamacpp-runtime.md) 7.4 |
| `curated-models.json` `schema_version: 2`, `artifacts.ollama` | `schema_version: 3` with a `variants` list — [`07`](07-llamacpp-runtime.md) 7.4 |
| `GET /llm/system`, `GET /llm/catalog`, `POST /llm/install`, `DELETE /llm/providers/{provider}/models/{name}` | Respecified in [`07`](07-llamacpp-runtime.md) **HTTP routes** |
| Catalog failure behavior, catalog tests, catalog acceptance | [`07`](07-llamacpp-runtime.md) **Failure behavior**, **Tests**, **Acceptance** |

Two pieces of this phase's reasoning survived the rewrite, and are worth naming
because phase 7 kept them rather than reinvented them:

- **A model no scan has scored is still installable.** This phase argued a
  curated row must render and install with no estimate behind it. Phase 7 goes
  further: `shape` in the manifest prices every curated row offline, on first
  paint, with no network at all.
- **Team-tested is not a claim about every computer.** This phase moved that
  claim out of the bucket and into the badge. Phase 7 keeps the split exactly —
  `rank` is a preference order over models we tested, the fit badge is
  subtraction, and the two are never rendered as the same thing.

## Prompt tiers

The live core of this phase, depended on by [`03-chat.md`](03-chat.md) and
[`../worker/04-studio.md`](../worker/04-studio.md).

A selected model is **fingerprinted at selection time**, and its fingerprint
decides which of three prompts it is given.

### Classification

`modules/llm/profile/` owns it. A `Fingerprint` carries `provider`, `name`, and
three nullable facts — `params_b`, `vendor`, and `line` (`flagship` or `small`) —
collected from the runtime's own inventory, from a remote connection's
`/models`, or, failing both, from heuristics on the name. `classify()` turns it
into a `Tier`:

| Known | Tier |
|---|---|
| `params_b` < `COMPACT_MAX_B` (7.0) | `compact` |
| `params_b` < `CAPABLE_MAX_B` (100.0) | `capable` |
| `params_b` ≥ 100.0 | `frontier` |
| no count, but a `vendor` | `frontier` |
| no count, `line` is flagship / small | `frontier` / `capable` |
| nothing, and the endpoint is **local** | `compact` |
| nothing, and the endpoint is **remote** | `capable` |

The thresholds encode a claim about scaffolding, not about quality: below the
first a model loses accuracy when asked to follow a structure, between the two it
gains from one, and above the second it writes better from judgement than from
steps. The last two rows are the same bet — a hosted endpoint runs models too big
for a laptop, a local one runs the laptop.

> **The last two rows must key on loopback, not on a provider name.** As built,
> `classify()` reads `provider == "ollama" → COMPACT`, which breaks the moment a
> Mac user runs a 4B through LM Studio and gets `capable` prompts for a compact
> model. `host_destination()` already computes loopback and returns `None` for
> it. Phase 7 makes this change alongside the provider rename —
> [`07`](07-llamacpp-runtime.md) **Decisions**, *Prompt tier fallback*.

Revision `0010` adds `params_b`, `vendor` and `line` to `selected_models`. **The
tier itself is not stored**: `SelectedModel.tier` calls `classify()` on read, so
retuning a threshold changes behaviour without a migration or a re-selection.
That is the property to preserve — it is what lets the two constants above move
on evidence rather than on a release.

### Loading

`modules/llm/prompting/` is the other half. `load(package, tier, case=None,
**slots)` reads `{package}/prompts/{tier}.md`, or
`{package}/prompts/{case}/{tier}.md` when a package has more than one prompt, and
fills `$slot` placeholders through `string.Template`; `focus()` appends the
user's steer as one line.

Every prompt lives as markdown beside the code that uses it: **23 cases × 3
tiers = 69 files**, covering chat, the `content/` formats, `office/`,
`web/html/`, the `media/visual/` formats, and podcast outline and draft
separately. A unit test asserts every case ships all three.

No `import` statement names any of them, so the PyInstaller specs collect them by
path, split along what each binary runs: `api.spec` takes only `modules.chat`'s
three, and `worker.spec` takes those plus every `*.md` under `worker.studio`.

> **What a tier carries will narrow.** [`07`](07-llamacpp-runtime.md) 7.8
> introduces constrained decoding — 48 of the 69 prompts demand JSON, and
> `response_format: {"type": "json_schema"}` makes malformed output mechanically
> impossible. Once format compliance no longer depends on persuasion, a tier
> carries **reasoning depth only**, which plausibly collapses three tiers to two.
> Nothing measures that today, so the split stands.

## Onboarding

Unchanged by phase 7, which lists `GET|POST /llm/onboarding` among the routes it
does not touch.

### `GET /llm/onboarding`

Returns whether the user has completed model onboarding.

### `POST /llm/onboarding`

Writes the durable completion marker. Requires a persisted generation selection.
Image is optional.

Two invariants worth restating, because both are easy to break from the
frontend: selecting or clearing a model **never** writes or resets this marker,
and Settings *Use* actions must not call this route.

## Selection storage

`SelectedModel(role)` stores the provider, the connection identity when remote,
the exact model id, and the three fingerprint facts. One row per role, so the
role is the primary key and choosing again updates in place.

- `provider` is the SurfSense inference provider, never the model publisher.
  llmfit's output overloaded that word; SurfSense DTOs say `publisher` for the
  other meaning. The distinction outlives llmfit and is worth keeping.
- Remote inventory is discovered live and never synchronized into SQLite — see
  [`05b-openai-compatible-connections.md`](05b-openai-compatible-connections.md).
- `"ollama"` becomes `"llamacpp"` in revision `0012`, which also clears
  selections pointing at weights the app no longer manages —
  [`07`](07-llamacpp-runtime.md) 7.6.

## Failure behavior

Narrowed to what this phase still owns.

- **No fingerprint facts at all**: `classify()` falls through to the loopback
  rule rather than raising. A wrong tier degrades prompt quality; it never fails
  a request.
- **A prompt file missing for a tier**: a packaging failure, caught by the unit
  test asserting all three exist per case, not handled at runtime.
- **Onboarding marker written without a selection**: rejected. The marker means
  the user finished choosing, and it is the one thing that must not become true
  early.

## Tests

- `classify()` across every row of the table above, including both endpoint
  rows, asserting a small local model served through a non-Ollama local endpoint
  is still `compact` once the loopback keying lands.
- `SelectedModel.tier` recomputes on read: changing `COMPACT_MAX_B` in a test
  changes the tier of an already-persisted row, with no migration.
- Every one of the 23 cases ships all three tier files.
- `load()` fills `$slot` placeholders; `focus()` appends exactly one line.
- Onboarding: the marker requires a persisted generation selection, and
  selecting or clearing a model leaves it untouched.
- Packaging: `api.spec` carries `modules.chat`'s three prompts and `worker.spec`
  carries every `*.md` under `worker.studio`, asserted on the frozen binary
  rather than the source tree.

## Acceptance

- Selecting a model records its fingerprint, and chat and every Studio format
  receive the tier that fingerprint implies.
- Retuning a tier threshold changes behaviour on the next request, with no
  migration and no re-selection.
- A local endpoint that is not Ollama receives `compact` prompts for a small
  model.
- Onboarding completes only with a generation selection persisted, and never
  resets when the selection changes.
