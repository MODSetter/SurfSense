# Frontend — Phase 5: Install UX

> Owns: the generation catalog and one-click install flow.
> API contract:
> [`../api/07-llamacpp-runtime.md`](../api/07-llamacpp-runtime.md).
>
> **Phase 7 supersedes the catalog half of this document** —
> [`../api/07-llamacpp-runtime.md`](../api/07-llamacpp-runtime.md) replaces
> Ollama with llama.cpp, deletes the hardware-scan gate, and changes the fit
> vocabulary. The sections below are updated to match it; anything describing
> `Scan hardware`, a `scanned` flag, five-level fit badges, `ollama_name`, or an
> llmfit-derived Explore list was true of phase 5 and is not true now. The
> OpenAI-compatible connection sections are unaffected.

## Goal

Make choosing a local generation model understandable without asking the user
to know RAM budgets, quantization, or GGUF files. Show the configurations
SurfSense has tested first, then a search over every GGUF model llama.cpp can
run, with an honest fit badge on every row.

## Onboarding

The **Choose your AI model** page loads `GET /llm/catalog` and renders:

1. **Recommended for this computer** — one entry, the highest-ranked curated
   model whose fit state is `FITS`.
2. **Tested by SurfSense** — the curated manifest, every row badged.
3. **All models** — a live Hugging Face search over 204,797 GGUF repos, ordered
   by downloads, via the separate search route. Absent when egress for
   `model_search` is off.
4. **Installed** — already available local models, plus **Add a .gguf file**.

`GET /llm/catalog` needs no network and returns rows 1, 2 and 4. Search is its
own request so the page never waits on `huggingface.co`.

This full-page flow appears only until durable model onboarding is complete.
Later model changes and recovery from a missing selection happen in
**Settings → Models** without returning to onboarding.

## Settings

The workspace rail keeps the Settings button, while `DashboardPage` owns the
dialog and its active section. The rail button opens General; a chat model error
opens Models directly.

The onboarding page and Models settings use the same model-selection content:
catalog, provider tabs, installation, refresh, and immediate Use actions.
Their shells remain separate. Local **Use** and remote **Use for chat** persist
the generation row and stay on the page. Onboarding leaves only when
**Start chatting** calls `POST /llm/onboarding`. The button stays disabled until a
chat model is persisted; Image is optional. Settings has no **Use selected
model** footer and does not complete onboarding.

Installed local generation models expose Delete after confirmation on
onboarding and in Settings → Models. Deleting the selected model clears the
backend selection but not onboarding completion. During setup, Start chatting
stays disabled until another chat model is chosen. After onboarding, the
dashboard remains available for reading chats and sources, disables sending,
and links back to Models settings. Remote and embedding-only models never show
local deletion controls.

Every settings section uses the same fixed-header, scrollable-body, and optional
fixed-footer shell. The dialog and its two-column grid constrain height with
`min-height: 0`; the section body is the only vertical scroll owner.

The composer model button opens a compact picker containing generation-capable
installed models. Users can search that list and switch models directly. A
separate **Manage models** action opens Settings → Models for downloads,
provider configuration, and hardware rescans.

**There is no hardware scan and no scan button.** The hardware line is present
on first paint: the budget comes from the runtime's own allocator in about
180 ms, so there is nothing to wait for and nothing to trigger. `Scan hardware`,
`Rescan hardware` and the `scanned` flag are all deleted.

**Every row carries a fit badge, in both lists**, because fit is arithmetic
rather than a judgement. Three states only, with no `Unknown`: every row has a
file size, so every row can be priced. Wording is per platform — see **Fit
states** in [`../api/07-llamacpp-runtime.md`](../api/07-llamacpp-runtime.md),
which owns the copy.

```text
●  Full speed        Runs entirely on the GPU
◐  Reduced speed     A little too big for the GPU. Most of it still fits.
◐  Reduced speed     Well over the GPU's memory. Expect it to be slow.
○  Won't fit         Needs about 21 GB. This Mac has 13.6 GB
```

**Reduced speed has two reason lines, chosen by `offload_fraction`**, which the
verdict carries. The verdict word does not change; only the explanation
sharpens, because one sentence is wrong at both ends of a range running from
barely noticeable to unusable.

A search row is badged from its file size alone and rendered as approximate
until its header is read, which happens when the row is opened.

Each card shows:

- model and family;
- parameter size and quantization;
- fit badge, plus one plain line of why;
- download size, context length, architecture;
- installed and selected state;
- `vision` when the model can read images. No other capability surfaces.

Search rows additionally show provenance (*quantized from `Qwen/Qwen3-8B`*),
download count, licence, and an **other quantizations** disclosure. They carry
**no rank and no quality claim** — we describe them, we do not judge them.

**Rank is never displayed.** It orders the curated rows within a fit state and
selects the ★; no number, score or star rating appears anywhere else.

## Interaction

- **Download & Use** sends only
  `POST /llm/install {"catalog_id": "...", "select": true}`. The renderer does
  not send a repo, file, artifact URL, local path, or quantization.
- Show bytes, percent, current phase, and cancellation while installing. Ignore
  duplicate clicks and keep other model actions disabled for a runtime that
  supports one pull at a time.
- A successful stream refreshes catalog and selected-model queries; chat becomes
  available only after the API reports installed and selected state.
- **Use** on an already installed compatible model calls the existing validated
  `PUT /llm/selection/generation` route.
- There is no rescan. `GET /llm/catalog` is cheap and needs no network; the
  hardware budget is re-read on each load.
- **Reduced speed installs like Full speed** — no confirmation dialog. It runs,
  slower, and llama.cpp places the layers. Only **Won't fit** blocks install,
  and it states required and available bytes and names a smaller model rather
  than greying out a control.
- **A Reduced speed model can carry the ★.** The recommendation gates on
  predicted speed, not on full residency — on a 6 GB card the best model to use
  is routinely one that spills a little. Measured: an RTX 3050 runs Qwen3 8B at
  roughly 28% on the CPU without noticeable lag, while a residency-only rule
  would have starred a 1.7B. Do not assume the ★ is always a **Full speed** row,
  and do not style it as though it were.
- Search shows a progress indicator while a row's header is fetched (2 to 3
  seconds) and resolves the approximate badge to a firm one.
- A failed or cancelled install remains retryable and is never shown as
  selected.
- **Delete** calls the backend's model endpoint. The renderer never edits the
  models directory. Deletion is unavailable during installs or active
  generation, and deleting the selected model never silently chooses another.

## States and degradation

- Nothing to skeleton on load: the hardware line, the curated rows and their
  badges all render without a network call or a probe the user has to start.
- llmfit is not shipped and cannot fail at runtime. Its numbers were baked into
  the manifest before release.
- If `model_search` egress is off or `huggingface.co` is unreachable, the search
  section reports the destination unavailable. Recommended, Tested and Installed
  are unaffected — that is the airgapped product.
- If a curated download 404s because the upstream repo moved, say the model is
  no longer available from this source and fall through to the next-best entry.
- If a runtime is unavailable, show its status and disable its install actions;
  other runtimes remain usable.
- If no model fits, explain the limitation and keep remote providers such as
  OpenAI-compatible connections available.
- Surface insufficient disk before progress starts with required and available
  bytes.
- Preserve keyboard focus across progress updates; progress announcements use
  a throttled live region rather than speaking every chunk.

## OpenAI-compatible connections

The shared model-selection content shows one Chat row and one Image row
above the tabs, labelled with `Local` or the connection name. Cards do not
repeat those roles.

```text
Chat  …  ·  Local | connection
Image …  ·  Local | connection
─────────────────────────────
Local | OpenAI-compatible
```

The remote tab implements
[`../api/05b-openai-compatible-connections.md`](../api/05b-openai-compatible-connections.md):

- render one compact card per named connection with its label, base URL,
  assigned Chat and Image models, **Browse models**, Edit, and Disconnect;
- add/edit asks for a label, base URL, and optional key; an existing key is
  represented only by `has_api_key`;
- when `/models` cannot verify an endpoint, show the reason and require an
  explicit **Save anyway** confirmation before enabling manual model-id entry;
- do not fetch remote catalogues while rendering cards; fetch a connection's
  models when **Browse models** opens and cache them while the card remains
  mounted;
- key list and row state by `(connection_id, model_name)`, since two endpoints
  may expose the same model id;
- connecting an endpoint does not select every discovered model and does not
  switch the active model;
- show exact model-id entry first in the browser, then live name search,
  All/Chat/Image/Unknown filters, and a fixed-height scrollable model list;
- each listed model offers **Use for chat** and **Assign as image**; the
  matching control becomes a disabled **In use** instead of a Chat/Image
  badge, and assigning either role keeps the browser open;
- allow exact model-id entry when a valid endpoint does not list the model;
- keep capability-unknown models visible and assignable instead of guessing
  from their names.

The Image filter is an aid, not an authority. It includes models positively
identified as image-capable and the current image selection. Assigning an
unknown model explains that the endpoint must implement
`/images/generations` or `/images`, then offers **Test image**, **Use without
testing**, and Cancel. Testing is user-triggered real inference and is never
run merely by opening the page. Image-only models returned by an endpoint's
optional `output_modalities=image` catalogue are merged into the same card.

Onboarding completes after one generation selection. Image is optional and
uses the same remote tab, not a separate provider setup screen. Disconnect
confirmation names any generation or image roles that will be cleared.

## Airgap

**Add a .gguf file** sits beside Installed, not buried as an advanced action —
with search unavailable offline, it is one of only two ways an airgapped user
gets a model. Electron supplies the selected file through a typed preload
method; the renderer never receives arbitrary filesystem powers. The adapter
validates the header, rejects an unsupported architecture, and links the file
into the models directory. Importing parser packs remains a separate packaging
flow.

## Frontend structure

```text
src/features/model-catalog/
├── api.ts
├── use-model-catalog.ts
├── model-catalog-page.tsx
├── model-family-group.tsx
├── model-card.tsx
├── install-progress.tsx
└── model-catalog.test.tsx

src/features/model-selection/
├── model-selection-content.tsx
├── provider-tab.tsx
├── connection-card.tsx
├── connection-form.tsx
├── remote-model-list.tsx
├── use-model-selection.ts
└── api.ts

src/features/onboarding/
├── onboarding-page.tsx
└── onboarding-page.test.tsx
```

TanStack Query owns catalog, installed inventory, and selection invalidation.
Search is a separate query with its own cache key and a 300 s stale time,
matching the API-side cache. The response shape is runtime-neutral; do not
branch rendering on a provider name. Fit-badge copy branches on the budget's
`uma` and `has_gpu` flags, not on the runtime.

## Acceptance

- A clean machine sees a hardware line, one ★ recommendation and every curated
  row badged, on first paint, with no button and no network.
- No screen anywhere displays a rank, score or star rating.
- Search returns results ordered by downloads, each badged, none ranked.
- Download & Use is one user action and ends with the exact installed model
  selected.
- Runtime failure, insufficient disk, a dead upstream pin, cancellation, and
  interrupted streams are represented without false success.
- With `model_search` egress off, Recommended, Tested and Installed still work
  and a `.gguf` can still be added from disk.
- Keyboard-only operation, visible focus, live progress, light/dark themes, and
  a narrow desktop window all work.
- Path B: install → model download → chat works after completion.
- Path A: import a valid local model/parser pack → app recognizes it.
- Packaged-app behavior matches development behavior.
- Two connections with the same model id render and select independently.
- Adding a connection makes its live models available but changes no role.
- Unknown image capability remains visible; explicit assignment and test
  behavior are clear.
- Disconnect clears only roles that reference that connection and never exposes
  its key.

## Needs from API

Catalog, search and install stream —
[`../api/07-llamacpp-runtime.md`](../api/07-llamacpp-runtime.md).
Binary/model packaging and airgap imports —
[`../api/05c-packaging.md`](../api/05c-packaging.md).
