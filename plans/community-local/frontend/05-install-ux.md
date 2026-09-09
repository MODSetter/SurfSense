# Frontend — Phase 5: Install UX

> Owns: the hardware-ranked generation catalog and one-click install flow.
> API contract:
> [`../api/05-model-recommendations.md`](../api/05-model-recommendations.md).

## Goal

Make choosing a local generation model understandable without asking the user
to know RAM budgets, quantization, Ollama tags, or GGUF files. Show exact
SurfSense-tested configurations first, then other installable catalog entries,
both ranked for the current computer.

## First-time setup

The **Choose your AI model** page loads `GET /llm/catalog` and renders:

1. **Best for this computer** — exact configurations from the curated-model manifest
   that fit this computer.
2. **More models** — remaining installable llmfit catalog entries.
3. **Installed** — already available local models, including models that are no
   longer a good fit under the current policy.

This full-page flow is only the startup gate when no generation model has been
selected. Later model changes happen in **Settings → Models**.

## Settings

The workspace rail keeps the Settings button, while `DashboardPage` owns the
dialog and its active section. The rail button opens General; a chat model error
opens Models directly.

The Models section reuses the catalog, provider, installation, and selection
logic from first-time setup. It puts Installed models first, supports local and
OpenRouter selection, and updates the dashboard's active selection immediately.
It does not render the onboarding page or its Continue action.

Every settings section uses the same fixed-header, scrollable-body, and optional
fixed-footer shell. The dialog and its two-column grid constrain height with
`min-height: 0`; the section body is the only vertical scroll owner.

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

## States and degradation

- Skeleton only the catalog region during the first scan; retain the page
  heading and hardware explanation.
- If llmfit is unavailable or malformed, show a recommendation warning and the
  installed-model controls returned by the API. Do not label unscored models as
  recommended.
- If a runtime is unavailable, show its status and disable its install actions;
  other runtimes remain usable.
- If no model fits, explain the limitation and keep remote providers such as
  OpenRouter available.
- Surface insufficient disk before progress starts with required and available
  bytes.
- Preserve keyboard focus across progress updates; progress announcements use
  a throttled live region rather than speaking every chunk.

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

## Needs from API

Normalized catalog and install stream —
[`../api/05-model-recommendations.md`](../api/05-model-recommendations.md).
Binary/model packaging and airgap imports —
[`../api/05-packaging.md`](../api/05-packaging.md).
