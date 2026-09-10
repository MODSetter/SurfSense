# Frontend — Phase 5: Install UX

> Owns: the hardware-ranked generation catalog and one-click install flow.
> API contract:
> [`../api/05a-model-recommendations.md`](../api/05a-model-recommendations.md).

## Goal

Make choosing a local generation model understandable without asking the user
to know RAM budgets, quantization, Ollama tags, or GGUF files. Show exact
SurfSense-tested configurations first, then other installable catalog entries,
both ranked for the current computer.

## Onboarding

The **Choose your AI model** page loads `GET /llm/catalog` and renders:

1. **Best for this computer** — exact configurations from the curated-model manifest
   that fit this computer.
2. **More models** — remaining installable llmfit catalog entries.
3. **Installed** — already available local models, including models that are no
   longer a good fit under the current policy.

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
**Continue** calls `POST /llm/onboarding`. Continue stays disabled until a
chat model is persisted; Image is optional. Settings has no **Use selected
model** footer and does not complete onboarding.

Installed local generation models expose Delete after confirmation. Deleting the
selected model clears the backend selection but not onboarding completion. The
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

Recommended entries are grouped visually by family (for example Qwen or Gemma),
but each card remains an exact parameter/quantization/runtime configuration.
Do not render every parameter size merely because its family is recommended.
An entry appears once only: Recommended models are removed from Explore.

Each card shows:

- model and family;
- parameter size and quantization when known;
- fit badge (`Perfect`, `Good`, `Marginal`, or `Too tight`);
- estimated memory, disk size, tokens/second, and usable context when present;
- runtime that will install it;
- installed and selected state;
- license and estimate-confidence details in disclosure text.

Missing estimates display `Unknown`; they are never rendered as zero. Use
plain-language fit labels, not raw llmfit scores, as the primary signal. A short
explanation says that estimates leave room for SurfSense itself and may differ
from real workloads.

## Interaction

- **Download & Use** sends only
  `POST /llm/install {"catalog_id": "...", "select": true}`. The renderer does
  not send an Ollama tag, artifact URL, local path, or quantization.
- Show bytes, percent, current phase, and cancellation while installing. Ignore
  duplicate clicks and keep other model actions disabled for a runtime that
  supports one pull at a time.
- A successful stream refreshes catalog and selected-model queries; chat becomes
  available only after the API reports installed and selected state.
- **Use** on an already installed compatible model calls the existing validated
  `PUT /llm/selection/generation` route.
- Manual **Rescan hardware** loads `GET /llm/catalog?refresh=true`. Ordinary
  navigation uses the cached scan.
- `Marginal` requires a confirmation that responses may be slow or fail at long
  context. `Too tight` cannot be newly installed but remains visible when
  already installed.
- A failed or cancelled install remains retryable and is never shown as
  selected.
- **Delete** calls the backend's provider model endpoint. The renderer never
  edits Ollama storage. Deletion is unavailable during installs or active
  generation, and deleting the selected model never silently chooses another.

## States and degradation

- Skeleton only the catalog region during the first scan; retain the page
  heading and hardware explanation.
- If llmfit is unavailable or malformed, show a recommendation warning and the
  installed-model controls returned by the API. Do not label unscored models as
  recommended.
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

Keep **Import local model** as an advanced secondary action. Electron supplies
the selected file/folder through a typed preload method; the renderer never
receives arbitrary filesystem powers. The API/runtime adapter validates the
artifact and imports atomically. Importing parser packs remains a separate
packaging flow and does not pass through llmfit.

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
The response shape is runtime-neutral; do not branch rendering on `ollama`
except for runtime-specific explanatory copy.

## Acceptance

- A clean supported machine sees hardware-ranked Recommended models above Explore.
- Gemma/Qwen family grouping does not create unsupported parameter-size cards.
- Download & Use is one user action and ends with the exact installed runtime
  model selected.
- Unknown estimates, llmfit failure, runtime failure, insufficient disk,
  cancellation, and interrupted streams are represented without false success.
- Installed models remain selectable when recommendation scanning is down.
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

Normalized catalog and install stream —
[`../api/05a-model-recommendations.md`](../api/05a-model-recommendations.md).
Binary/model packaging and airgap imports —
[`../api/05c-packaging.md`](../api/05c-packaging.md).
