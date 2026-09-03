# Phase 12 — Preset-Gated Infographic Artifacts

**Status:** Planned.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 1 artifact persistence and manifests, phase 3 signed
verification receipts and visual review, phase 7 format-level rendering and
source binding, phase 10 public artifact access, and the existing checkpointed
LangGraph interrupt/resume path.
**Independent of:** a future agent-authored `ask_user` tool. Phase 12 builds the
generic structured-question protocol and UI, but only trusted backend presets
may create questions in this phase.

## 1. Goal

Add generated infographics as first-class artifacts through the universal
artifact flow while collecting visual-style preference through a preset-driven
human-in-the-loop gate:

```text
load_artifact_instructions("infographic")
  -> structured-question interrupt("infographic.visual-style.v1")
  -> user chooses a visual style above the composer
  -> resume the same checkpointed artifact run
  -> generate infographic image into the artifact workspace
  -> verify_artifact(path=..., format="infographic", markdown_path=...)
  -> save_artifact(path=..., markdown_representation=...)
```

An infographic artifact:

- is semantically distinct from an ordinary generated image;
- uses the workspace's configured image-generation model;
- asks the user only for a visual-style preset in version one;
- receives question content from a trusted, versioned backend preset, never
  from the agent;
- renders the question through one generic structured-question panel above the
  main composer;
- pauses and resumes through the existing durable LangGraph checkpoint;
- compiles the selected preset into detailed model-facing prompt directives;
- stores one normalized PNG as its primary file;
- binds a searchable Markdown representation to the exact verified PNG;
- records selected style, resolved style, preset version, prompt-recipe
  version, and image-model provenance;
- renders in the ordinary artifact panel and mobile drawer;
- downloads through the ordinary artifact download route;
- revises through the ordinary optimistic-generation artifact workflow.

This phase adds one semantic artifact format, one sandbox skill, one
backend-internal image-generation stage inside the unified artifact invocation,
one trusted preset catalog, one prompt compiler, one structured-question
interrupt variant, and one generic composer-level question UI.

It does not add:

- a dedicated `create_infographic`, `prepare_infographic`, or
  `save_infographic` agent tool;
- an agent-facing `ask_user` tool;
- agent-authored question text or options;
- a second artifact table, file role, panel, search leg, citation kind, or
  public API family;
- a visual-style database table or user-authored preset marketplace;
- image-model selection in the preset UI;
- a separate infographic job model or queue;
- editable vector source, in-panel design editing, or historical generations.

## 2. Product and scope decisions

### 2.1 Preset-driven now, agent-authored later

Phase 12 separates the **question transport and renderer** from the **producer
of question content**.

The only phase-12 producer is:

```text
request_preset_questions("infographic.visual-style.v1")
```

The infographic workflow invokes this preset automatically. The agent does not
decide whether to ask, does not write the question, and does not choose its
options.

The generic wire shape deliberately permits another producer in the future:

```text
future ask_user tool -> validated agent-authored questions
```

That future tool is out of scope. No `ask_user` name is registered, advertised
in a prompt, or made available to any main agent or subagent in phase 12.
Origin is trusted server metadata, never an argument an agent or browser may
choose.

### 2.2 Visual style is the only required choice

The version-one preset asks exactly one required question:

> Choose a visual style

Initial options are:

1. `auto` — choose a suitable concrete style from the current catalog;
2. `kawaii` — playful rounded illustration with pastel color and bold outlines;
3. `clay` — tactile three-dimensional clay forms with soft studio lighting;
4. `sketch-note` — hand-drawn ink, arrows, annotations, and restrained color;
5. `anime` — polished cel-shaded illustration with energetic composition.

`auto` is selected by default. The UI may show more than four options in a
horizontal carousel. A future agent-authored question policy may cap agent
questions at four options without imposing that limit on trusted product
presets.

Phase 12 does not ask for:

- image model;
- aspect ratio;
- palette;
- detail level;
- source selection;
- audience;
- tone;
- number of sections;
- confirmation of agent-inferred content.

The agent infers safe content structure from the request and sources. An
explicit aspect ratio or audience in the user's request is honored. Otherwise,
the infographic skill uses its documented defaults. Additional preset
questions require a new preset version and product evidence that the choice
improves outcomes enough to justify another interruption.

### 2.3 Non-modal composer-level interaction

The visual-style selector appears directly above the main composer in the
sticky `ChatViewport` footer. It is visually elevated like a popup but is not a
modal dialog and is not implemented as a trigger-based popover.

While the structured question is pending:

- the thread remains durably paused;
- ordinary message submission is disabled;
- the composer remains visible but clearly unavailable for a competing turn;
- the selector receives keyboard focus without trapping focus;
- navigation away is legal;
- revisiting or refreshing restores the pending selector from the checkpoint;
- submission enters a processing state until resume is accepted;
- cancellation ends the infographic workflow without generating or saving an
  artifact.

The question is not duplicated inside the assistant-message timeline. After a
successful response, the transient selector disappears. The eventual artifact
manifest preserves the chosen style; phase 12 does not add a permanent
question/answer chat bubble.

### 2.4 Infographic and ordinary image are separate intents

The distinction is semantic, not based on the `.png` suffix:

```text
Standalone illustration, photo, icon, wallpaper, concept art, or ordinary
"generate an image" request
  -> generate_image
  -> Artifact(format="image")
  -> inline generated-image card

Infographic, visual explainer, visual comparison, process infographic,
data story, information poster, or infographic-style summary
  -> load_artifact_instructions("infographic")
  -> preset HITL
  -> verify + save universal artifact workflow
  -> Artifact(format="infographic")
  -> ordinary artifact card and panel
```

An explicit infographic request wins even when the user also says “image,”
“picture,” or “graphic.” An ordinary image request never triggers the preset
selector. A request for a chart whose primary value is exact quantitative
plotting remains a deterministic document/chart workflow rather than an image
model infographic.

The existing `generate_image` tool description must explicitly exclude
infographics and information-dense artifacts. The deliverables system prompt
must place infographic routing ahead of standalone image routing and generic
PDF/HTML defaults.

### 2.5 Image models create the visual, trusted code owns the workflow

The selected preset affects the image-generation prompt; it is not merely
frontend decoration. The browser submits only stable answer IDs. Trusted
backend code resolves those IDs into versioned style directives and compiles
the final prompt.

The agent may author the infographic's factual content outline and hierarchy,
but it may not:

- define or override preset prompt recipes;
- submit raw style prompt fragments from the UI;
- reinterpret `kawaii` or another style differently per run;
- replace the user's selected style;
- claim that `auto` was used without persisting its concrete resolution.

### 2.6 Text reliability boundary

Image-generation models can misspell labels, hallucinate facts, duplicate
sections, and render small text poorly. Phase 12 therefore requires:

- bounded visible copy;
- short headings and labels;
- a trusted Markdown content representation;
- visual verification with OCR-oriented checks;
- one bounded regeneration after consolidated blocking findings;
- failure without save when the second verification still has blockers.

Phase 12 does not claim pixel-perfect typography or deterministic rendering.
If production evidence shows that model-rendered text cannot meet the quality
bar, the upgrade path is a hybrid renderer: image models create illustrations
or backgrounds while trusted HTML/SVG code lays out factual text. That renderer
must be introduced as a later format revision rather than silently changing
the phase-12 contract.

## 3. Architecture and data flow

### 3.1 Components

```text
Deliverables subagent
  |
  | load_artifact_instructions("infographic")
  v
Infographic workflow gate
  |
  | resolve trusted preset
  | interrupt(StructuredQuestionInterrupt)
  v
Existing LangGraph checkpointer
  |
  | interrupt-request SSE
  v
Generic StructuredQuestionPrompt above composer
  |
  | StructuredQuestionResponse
  v
Existing /threads/{thread_id}/resume route
  |
  | Command(resume=...)
  v
Resumed infographic workflow
  |
  | validate answers against exact preset version
  | resolve auto style
  | compile model prompt
  v
Shared image-generation service
  |
  | normalized PNG written to sandbox artifact workspace
  v
verify_artifact("infographic") -> save_artifact
  |
  v
Document + Artifact + ArtifactFile
```

### 3.2 Boundaries

- **Preset catalog:** owns selectable styles, display metadata, recipe
  versions, and model-facing directives.
- **Structured-question protocol:** owns bounded transport, durable interruption,
  response validation, and restoration; it knows nothing about infographics.
- **Generic question UI:** owns selection interaction only; it renders server
  data and submits stable answer IDs.
- **Prompt compiler:** owns conversion from factual content + resolved preset +
  provider capabilities into an image-generation request.
- **Image-generation service:** owns model resolution, billing, provider calls,
  temporary-URL fetching, MIME sniffing, and byte normalization.
- **Infographic adapter:** owns image/Markdown verification policy and semantic
  format identity.
- **Artifact service:** remains format-blind and owns persistence, revision,
  indexing, blobs, manifests, download, and deletion.

No boundary is introduced solely because the UI calls the interaction a
“preset.” The generic protocol has no dependency on the preset catalog, and
the artifact persistence service has no dependency on either.

## 4. Structured-question interrupt contract

### 4.1 Request

Add a discriminated interrupt payload:

```json
{
  "interrupt_type": "structured_question",
  "origin": {
    "kind": "preset",
    "preset_id": "infographic.visual-style",
    "preset_version": 1
  },
  "title": "Customize your infographic",
  "description": "Choose how the infographic should look.",
  "questions": [
    {
      "id": "visual_style",
      "prompt": "Choose a visual style",
      "required": true,
      "allow_multiple": false,
      "allow_other": false,
      "default_option_ids": ["auto"],
      "presentation": "visual_cards",
      "options": [
        {
          "id": "auto",
          "label": "Auto-select",
          "description": "Choose a suitable style automatically.",
          "preview_asset": "infographic-style/auto"
        },
        {
          "id": "kawaii",
          "label": "Kawaii",
          "description": "Playful pastel illustration with rounded forms.",
          "preview_asset": "infographic-style/kawaii"
        },
        {
          "id": "clay",
          "label": "Clay",
          "description": "Soft three-dimensional clay forms.",
          "preview_asset": "infographic-style/clay"
        },
        {
          "id": "sketch-note",
          "label": "Sketch Note",
          "description": "Hand-drawn notes, arrows, and restrained color.",
          "preview_asset": "infographic-style/sketch-note"
        },
        {
          "id": "anime",
          "label": "Anime",
          "description": "Energetic cel-shaded illustration.",
          "preview_asset": "infographic-style/anime"
        }
      ]
    }
  ]
}
```

`origin` is created by trusted server code. It is not accepted from an agent,
tool argument, or resume request.

### 4.2 Bounds

Keep bounds in one backend schema and mirror them in the frontend parser:

- at most 4 questions per interrupt;
- at most 12 options per trusted preset question;
- IDs: 1–64 ASCII characters matching a conservative slug pattern;
- title: at most 120 Unicode code points;
- description: at most 500 code points;
- prompt: at most 500 code points;
- option label: at most 80 code points;
- option description: at most 240 code points;
- no duplicate question or option IDs;
- defaults must reference listed option IDs;
- single-select questions have at most one default;
- required questions must have a default or require explicit selection;
- preview assets are allowlisted logical keys, not arbitrary URLs;
- unknown fields fail validation.

The phase-12 infographic preset uses one single-select question with five
options and no free-text input.

### 4.3 Response

Do not overload approval `approve`, `edit`, or `reject` decisions. Add a
semantic structured-question response:

```json
{
  "type": "respond",
  "interrupt_id": "langgraph-interrupt-id",
  "answers": [
    {
      "question_id": "visual_style",
      "selected_option_ids": ["kawaii"]
    }
  ]
}
```

Cancellation is explicit:

```json
{
  "type": "cancel",
  "interrupt_id": "langgraph-interrupt-id"
}
```

The browser never submits labels, descriptions, prompt fragments, preset
origin, preset version, model ID, or provider parameters.

The backend validates the response against the exact pending preset:

- every required question is answered;
- every question ID belongs to the preset;
- every selected option ID belongs to that question;
- selection cardinality matches `allow_multiple`;
- duplicate selections fail;
- unknown answers fail;
- a stale or already-consumed interrupt fails closed;
- preset version mismatch never silently upgrades a paused run.

### 4.4 Resume compatibility

Preserve the existing approval wire and endpoint behavior. Extend the resume
request with typed interrupt responses rather than changing the meaning of
`decisions`.

The route must support:

- approval-only pending interrupts;
- structured-question-only pending interrupts;
- multiple parallel approval interrupts;
- a mixed set of approvals and structured questions;
- one resume only after every pending interrupt has a response;
- mapping by LangGraph interrupt ID;
- existing parent/subagent tool-call routing where the checkpointed-subagent
  bridge also requires an owning tool-call ID.

The page-level pending-response coordinator becomes generic: it stages one
typed response per pending interrupt and sends one ordered resume request when
all are complete. Existing approval cards continue producing their unchanged
decision arrays.

### 4.5 LangGraph execution rules

`interrupt()` restarts the containing node/tool from the beginning on resume.
Therefore the infographic gate must:

1. construct and validate the preset deterministically;
2. call `interrupt()` before opening a sandbox, reserving credits, invoking a
   model, writing a database row, or writing a file;
3. validate the returned answer;
4. perform generation only after a valid response;
5. use idempotency keys for any later operation that may retry.

The order and number of interrupts in the node must remain stable for a paused
preset version. A code deployment must not mutate an existing preset version;
add version 2 instead.

## 5. Trusted visual-style preset catalog

### 5.1 Ownership

Add a backend-owned infographic domain:

```text
surfsense_backend/app/artifacts/infographic/
  __init__.py
  schemas.py
  presets.py
  prompt.py
  generation.py
```

`presets.py` is the source of truth for IDs, versions, display metadata,
auto-selection eligibility, and prompt recipes. Do not place recipe definitions
in:

- React components;
- `SKILL.md`;
- agent system prompts;
- database rows;
- tool descriptions;
- resume payloads;
- browser local storage.

The sandbox skill explains how to consume a resolved style but does not define
what a style means.

### 5.2 Recipe model

Each concrete style contains:

```python
VisualStylePreset(
    id="sketch-note",
    version=1,
    label="Sketch Note",
    preview_asset="infographic-style/sketch-note",
    prompt_directives=VisualStyleDirectives(
        medium="hand-drawn editorial sketchnote illustration",
        palette="mostly black ink on warm white with one restrained accent color",
        shapes="simple icons, arrows, connectors, frames, and loose organic lines",
        texture="subtle paper texture; no photographic texture",
        lighting="flat illustration; no cinematic lighting",
        composition="clear visual hierarchy with generous whitespace and grouped notes",
        typography="short hand-lettered headings and highly legible labels",
        avoid=(
            "photorealism",
            "dense paragraphs",
            "decorative illegible handwriting",
            "watermarks",
        ),
    ),
)
```

Recipes describe medium, palette behavior, shapes, texture, lighting,
composition, typography character, and exclusions. They must not contain user
facts, source text, credentials, provider secrets, or model IDs.

### 5.3 Auto selection

`auto` is a selector, not a concrete prompt recipe. Resolve it before prompt
compilation to one concrete phase-12 style.

Resolution is deterministic and bounded:

- use explicit content signals from the normalized infographic brief;
- never call another LLM solely to choose a style;
- use a stable default when no rule matches;
- record both requested and resolved IDs;
- never resolve to a preset unavailable in the exact catalog version.

Suggested initial rules:

- playful, children, beginner, friendly, or cute content -> `kawaii`;
- tactile product, craft, object, or physical-process content -> `clay`;
- study notes, brainstorming, teaching, or conceptual explanation ->
  `sketch-note`;
- entertainment, gaming, manga, or explicitly dynamic content -> `anime`;
- otherwise -> `sketch-note`.

Rules are product heuristics, not semantic truth. Keep them short and covered
by table-driven tests.

### 5.4 Preview assets

Store app-owned optimized preview images under a stable frontend asset path,
for example:

```text
surfsense_web/public/infographic-styles/
  kawaii.webp
  clay.webp
  sketch-note.webp
  anime.webp
```

`auto` uses a local icon rather than a generated preview. Backend payloads
carry logical allowlisted asset keys. A frontend mapping resolves each key to a
bundled path. No remote image URL, provider URL, data URL, or user-controlled
asset is accepted.

Preview images are representative examples, not model guarantees. Their alt
text is the option label plus description.

## 6. Infographic prompt compiler

### 6.1 Inputs

The compiler receives:

- normalized user intent;
- grounded factual content and source references;
- planned title, sections, labels, and hierarchy;
- explicit user constraints such as audience or aspect ratio;
- requested style ID;
- resolved concrete style and recipe version;
- resolved image-model capabilities;
- retry findings when performing the one allowed repair.

It must not receive frontend-authored prompt fragments.

### 6.2 Layering

Compile the final prompt in a stable order:

1. **Task identity:** explicitly request one complete infographic, not a
   standalone scene or decorative illustration.
2. **Factual contract:** enumerate the exact title, headings, labels, numbers,
   relationships, and ordering.
3. **Information architecture:** state hierarchy, reading direction, grouping,
   whitespace, and section count.
4. **Visual recipe:** apply the resolved style directives.
5. **Legibility:** require short readable text, strong contrast, and no tiny
   labels or paragraph blocks.
6. **Output constraints:** aspect ratio, single canvas, no crop, no mockup
   frame, and no external branding.
7. **Negative constraints:** watermarks, invented facts, duplicated sections,
   unreadable text, clipped content, UI chrome, stock-template placeholders,
   and recipe-specific exclusions.
8. **Repair guidance:** on the single retry, append consolidated verifier
   findings without discarding the original factual contract.

The compiler returns a typed request plus a redacted provenance summary. It
does not mutate the preset object.

### 6.3 Content bounds

The skill and compiler should target:

- one title;
- 3–7 sections;
- at most 12 visible numeric facts;
- at most 40 short visible labels;
- headings at most 60 code points;
- labels at most 120 code points;
- no paragraph longer than 240 code points;
- no unsupported control characters;
- no raw HTML or Markdown formatting instructions in visible labels.

These are generation-quality bounds, not a claim about every provider's pixel
capacity. Over-dense source material must be summarized or split before model
invocation. Phase 12 creates one complete infographic, not an unreadable wall
of text.

### 6.4 Provider adaptation

Use the installed LiteLLM image-generation path, but keep provider differences
inside the shared image-generation service:

- resolve the workspace image model exactly as ordinary image generation does;
- pass portable visual style primarily through the prompt;
- map aspect ratio or size only when the resolved provider declares support;
- accept provider URL or base64 responses;
- fetch temporary URLs immediately;
- validate decoded bytes;
- normalize supported output to PNG;
- strip unneeded metadata;
- record the actual model and normalized dimensions.

Do not send a provider-native `style` parameter merely because another
provider supports a similarly named value. Preset semantics are SurfSense
semantics and must remain stable across models.

## 7. Image generation inside the unified artifact invocation

### 7.1 Share a service, not standalone-image persistence

The current `generate_image` tool combines:

- workspace model resolution;
- capability checks;
- billing;
- LiteLLM invocation;
- provider response normalization;
- immediate `Artifact(format="image")` persistence;
- inline chat result construction.

Extract or reuse the first five responsibilities through one shared
image-generation service. Keep persistence and inline UI result construction
in the standalone tool. The unified infographic workflow invokes only the
shared service, then continues through universal artifact verification and
save.

```text
ImageGenerationService.generate(...)
  ├── generate_image tool
  │     -> record ordinary image artifact
  │     -> inline image card
  └── unified infographic artifact invocation
        -> write normalized PNG to sandbox path
        -> verify infographic
        -> save_artifact
        -> configured artifact blob backend
```

Calling the existing standalone `generate_image` behavior from the infographic
workflow is prohibited because it would create an extra `format="image"`
artifact and inline image card before the real infographic is saved.

### 7.2 One checkpointed unified-artifact invocation

Do not register a new infographic tool and do not add a staging mode to the
public `generate_image` tool schema.

The main agent delegates one infographic request to the existing deliverables
route. That checkpointed deliverables invocation owns the complete lifecycle:

```text
intent routing
  -> load infographic instructions
  -> preset interrupt
  -> resume
  -> compile factual + visual-style prompt
  -> invoke shared image-generation service internally
  -> stage normalized PNG and canonical Markdown in the sandbox
  -> verify both exact files
  -> save_artifact
  -> return the save receipt
```

The model does not call `generate_image` anywhere in this path. Ordinary
`generate_image(prompt, n)` retains its current standalone behavior and public
schema. The infographic workflow reaches the provider through a trusted
backend-internal operation scoped to the active deliverables invocation.

The generated PNG may exist temporarily under an allowed `/workspace/...png`
path so existing verification and `save_artifact` can consume it. That path is
staging only: it is not a durable artifact location, is not returned as final
output, and may disappear when the sandbox session ends.

Do not expose `persist=false`, `artifact_mode`, a raw provider endpoint, or an
arbitrary host-write capability to the agent. Workflow identity, workspace,
thread, billing context, and destination are supplied by trusted runtime state.

### 7.3 Billing and retries

- Reserve and settle image-generation usage through the existing billable-call
  path.
- The HITL pause consumes no image-generation reservation.
- Cancellation before resume consumes no generation credits.
- Provider failure produces no artifact.
- Verification failure permits one regeneration with consolidated findings.
- The second provider call is separately billed and recorded.
- No unbounded automatic fallback loop exists.
- Automatic model fallback, if already supported by the shared service, must
  preserve the selected SurfSense preset and record the actual model used.

## 8. Persistence and semantic format identity

An infographic is:

- one `Document(document_type=ARTIFACT)` containing searchable Markdown;
- one `Artifact(format="infographic")`;
- one primary normalized `<slug>.png` with MIME `image/png`;
- no preview file.

Add `INFOGRAPHIC = "infographic"` to `ArtifactFormat` for typed callers. The
database format column remains a string; no Alembic migration is required.

The PNG owns downloadable and visual bytes. The Markdown owns indexing,
search, citations, accessibility fallback, revision context, and factual
comparison during verification.

`.png` and `image/png` identify only physical representation. Explicit
`format="infographic"` in the receipt, artifact row, manifest, format metadata,
and verifier distinguishes an infographic from:

- `format="image"` generated images;
- `format="mindmap"` PNG downloads;
- generic PNG fallback files.

### 8.1 Searchable Markdown

Create one canonical Markdown file in the sandbox:

```markdown
# The Water Cycle

## Summary

A visual explanation of evaporation, condensation, precipitation, and collection.

## Sections

1. Evaporation — Solar heat turns surface water into vapor.
2. Condensation — Cooling vapor forms clouds.
3. Precipitation — Water returns as rain or snow.
4. Collection — Water accumulates in rivers, lakes, oceans, and soil.

## Visual style

Sketch Note
```

The Markdown:

- contains all factual statements and visible labels requested from the model;
- preserves meaningful ordering and relationships;
- includes the resolved style label but not raw prompt directives;
- contains useful alt-text-level summary;
- excludes provider secrets, model responses, hidden reasoning, and raw
  base64;
- remains bounded by the existing artifact Markdown limit.

The signed verification receipt binds both the PNG hash and Markdown hash.
`save_artifact` rejects either file changing after verification.

### 8.2 Metadata

Persist format-owned metadata under a bounded namespace:

```json
{
  "infographic": {
    "schema_version": 1,
    "question_preset_id": "infographic.visual-style",
    "question_preset_version": 1,
    "requested_style_id": "auto",
    "resolved_style_id": "sketch-note",
    "style_recipe_version": 1,
    "image_model_id": 42,
    "provider_model": "provider/model",
    "width": 1536,
    "height": 1024
  }
}
```

Do not expose raw provider responses or complete prompts in the public
manifest. Operational provenance may retain a bounded prompt hash and
redacted request summary where existing policy permits.

### 8.3 Durable blob storage

`save_artifact` is the only durable storage boundary for the generated
infographic. After receipt validation, it reads the exact verified PNG and
passes it through the existing artifact service and
`store_artifact_file`/`store_artifact_file_stream` path.

The storage backend remains deployment-configured:

```text
save_artifact
  -> artifact service
  -> get_storage_backend()
       -> AzureBlobBackend in Azure-backed deployments
       -> LocalFileBackend in local/self-hosted deployments
  -> ArtifactFile(storage_backend, storage_key, checksum_sha256, ...)
```

The infographic implementation must not:

- upload directly to Azure;
- store image bytes in PostgreSQL;
- persist a provider URL;
- treat the Docker/OpenSandbox filesystem as durable storage;
- create a second infographic-specific upload route;
- bypass artifact blob keys, checksums, rollback cleanup, or revision cleanup.

In production, the primary PNG lives in the configured external Azure
container when Azure is selected. In local Docker development, the same
artifact API may resolve to the configured local storage root, which must use
the deployment's persistent volume when durability across container recreation
is required. `ArtifactFile` stores backend identity, immutable key, MIME, size,
and checksum; the database does not store the PNG body.

Only after blob storage and artifact/document persistence succeed may the tool
return the ordinary `save_artifact` success receipt. The chat card, artifact
panel, immutable content route, stable download route, public route, and
artifact library all resolve the same stored primary through the manifest.

## 9. Verification

### 9.1 Adapter

Register an infographic adapter:

```python
FormatAdapter(
    name="infographic",
    suffix=".png",
    mime_type="image/png",
    convert_to_pdf=False,
    check=check_infographic_png,
    requires_visual_review=True,
    requires_markdown_binding=True,
)
```

Phase 12 must reuse the existing receipt and `requires_markdown_binding` seams
rather than add format-specific save logic. Generalize the current
mind-map-specific hash-mismatch error text in `save_artifact` so the shared
binding failure accurately names any adapter that requires Markdown binding.

### 9.2 Programmatic checks

Before vision review:

- require a valid PNG signature and successful complete decode;
- reject empty, truncated, animated, multi-frame, or unsupported images;
- enforce existing byte and decoded-pixel ceilings;
- require width and height within configured bounds;
- require an allowed aspect-ratio range;
- reject fully transparent, single-color, or effectively blank output;
- reject suspicious trailing bytes or decompression bombs;
- validate Markdown encoding, size, and required structure;
- sign exact PNG and Markdown hashes.

### 9.3 Visual review

Provide the verifier with:

- the exact PNG;
- the exact Markdown factual representation;
- the selected concrete style label and bounded style expectations;
- the generation brief;
- no credentials or full provider response.

Blocking findings include:

- title, key label, or critical number is missing or materially misspelled;
- visible facts conflict with the Markdown;
- sections are duplicated or omitted;
- content is clipped, overlapped, or unreadably small;
- hierarchy or reading direction is unusable;
- output is primarily a decorative illustration rather than an infographic;
- user-selected style is materially absent;
- watermark, mockup frame, placeholder, or unexplained branding appears;
- unsafe or disallowed content appears.

Advisory findings include minor aesthetic imbalance that does not impair
meaning or legibility.

The first failed review returns all bounded actionable findings together. The
workflow recompiles one repair prompt and regenerates once. A persistent
blocking finding stops without calling `save_artifact`.

Visual review does not claim mathematical proof of factual correctness. It is
a bounded consistency and usability gate over model-authored pixels.

## 10. Generation skill and intent routing

### 10.1 Skill

Add:

```text
docker/sandbox/skills/infographic/SKILL.md
```

Advertise `"infographic"` through `load_artifact_instructions`.

The skill teaches the agent to:

1. use infographic only for explicit information-visualization intent;
2. let the workflow present the trusted visual-style preset;
3. never ask the user for that style in ordinary chat;
4. consume the resolved style returned after resume;
5. create a concise factual hierarchy and Markdown representation;
6. compile generation through the trusted backend prompt path;
7. stage one normalized PNG at the required workspace path;
8. call `verify_artifact(path=..., format="infographic", markdown_path=...)`;
9. repair all blocking findings together and regenerate at most once;
10. reverify the exact PNG and Markdown;
11. call the existing `save_artifact` only after verified;
12. stop after a persistent blocker.

The skill must not define preset recipes. It refers to the resolved directives
supplied by the workflow and prohibits overriding them.

### 10.2 Routing updates

Update:

- deliverables `system_prompt.md`;
- deliverables `description.md`;
- `tools/sandbox.py` artifact-type literal;
- the existing `generate_image` tool description;
- installed-skill roster tests;
- intent-routing tests;
- `load_artifact_for_revision` format guidance.

Required routing rules:

- explicit infographic or visual-explainer intent selects `infographic`;
- “make an image infographic” still selects `infographic`;
- ordinary image, illustration, photograph, icon, wallpaper, and concept-art
  requests select `generate_image`;
- exact charts and plots do not silently select image-model infographic;
- mind maps remain `mindmap`;
- slide decks remain `pptx`;
- printable text-heavy one-pagers remain `pdf` unless infographic intent is
  explicit;
- interactive data exploration remains `html`;
- ordinary summaries remain documents.

No new completion emitter or chat tool card is introduced. Successful
generation still completes through `save_artifact`.

## 11. Generic structured-question frontend

### 11.1 Placement

Mount a generic `StructuredQuestionPrompt` in the existing `ChatViewport`
footer immediately before the main `Composer`.

It consumes pending interrupts through the existing page-level pending
interrupt provider. Do not use `WorkspaceSplit.overlay`, a modal dialog, or an
inline assistant-message approval card.

The footer owns:

```text
PremiumQuotaPinnedAlert
StructuredQuestionPrompt (when pending)
Composer
```

### 11.2 Rendering

The generic renderer branches only on protocol fields:

- `presentation="visual_cards"` -> thumbnail card carousel;
- a future ordinary option presentation -> text option list;
- `allow_multiple` -> checkbox semantics;
- otherwise -> radio-group semantics;
- `allow_other` -> bounded free-text field when later enabled.

It contains no infographic IDs, labels, recipes, model logic, or special-case
question text.

For the phase-12 preset:

- show title and optional description;
- show one horizontally scrollable row of visual cards;
- show the local preview, label, and concise description;
- mark `auto` selected initially;
- expose previous/next scroll buttons only when content overflows;
- keep native horizontal touch scrolling;
- show one primary `Continue` action;
- show one secondary `Cancel` action;
- prevent duplicate submission;
- show a processing state while resume is in flight.

### 11.3 State

Persisted/checkpoint-owned:

- pending interrupt ID;
- preset identity and version;
- complete question payload;
- whether the graph is awaiting a response.

Local:

- current selections before submission;
- carousel scroll position;
- overflow-arrow visibility;
- focus and transient validation state;
- resume-request pending/error state.

Selections initialize from validated `default_option_ids`. Local state resets
when the interrupt ID changes. It does not survive navigation independently;
the restored interrupt recreates canonical defaults.

### 11.4 Timeline integration

The interleaved timeline currently mounts approval cards for pending
interrupts. Structured-question interrupts must be filtered from that path and
rendered only in the composer footer.

Approval interrupts remain inline and unchanged. A mixed turn may therefore
show:

- approval cards in the timeline; and
- one structured-question prompt above the composer.

Resume occurs only after every pending interrupt has a staged response. The UI
must explain when another approval remains rather than appearing stuck after
the question is submitted.

### 11.5 Accessibility and responsive behavior

- Use an accessible labelled radio group for the visual-style question.
- Each card is a complete label/click target.
- Selection is communicated by icon/border and accessible checked state, not
  color alone.
- Arrow keys move among options; Tab reaches actions.
- The horizontal region has an accessible name and does not trap focus.
- Preview images have concise alt text and fixed dimensions to avoid layout
  shift.
- Submission errors use a bounded live region.
- Focus moves to the question heading when restored and back to the composer
  after cancellation or successful completion when appropriate.
- Reduced motion disables entrance/selection movement without hiding state.
- Mobile uses the same component full-width above the composer.
- Touch scrolling the option row must not drag-dismiss a surrounding mobile
  drawer.

## 12. Manifest, rendering, download, and public access

### 12.1 Manifest

The ordinary artifact manifest remains sufficient:

```json
{
  "artifact_id": 123,
  "format": "infographic",
  "generation": 1,
  "title": "The Water Cycle",
  "markdown_representation": "# The Water Cycle\n...",
  "files": [
    {
      "role": "primary",
      "filename": "the-water-cycle.png",
      "mime_type": "image/png",
      "content_url": "..."
    }
  ]
}
```

If style metadata is exposed to authenticated clients, return a sanitized
format-scoped view containing IDs, versions, and labels only. Do not return raw
prompt recipes or provider response payloads.

### 12.2 Renderer

Add format metadata:

- icon: existing image/chart-oriented icon;
- label: `Image`;
- detail label: `Infographic`;
- group: `Files`;
- viewing mode: `viewer`.

The ordinary image MIME viewer can display the PNG, but semantic format
dispatch and labels must remain `infographic`. Do not teach generic
`image/png` dispatch that every PNG is an infographic.

Show:

- fit-to-panel image;
- zoom controls already supported by the artifact panel;
- Markdown-derived accessible summary where the image viewer supports one;
- ordinary download action.

Do not add an infographic editor, regenerate button, preset selector, or
provider controls inside the viewer.

### 12.3 Download and public access

The stable artifact download returns the primary PNG as an attachment with a
safe filename. Immutable content may use existing image-serving policy where
appropriate.

Phase 10 public routes expose the allowlisted current infographic generation
through the same manifest, content, and download authorization. Public viewers
do not expose model configuration, full prompts, or private checkpoint data.
The preset question itself is part of generation and never appears on a public
artifact page.

## 13. Revision

`load_artifact_for_revision(artifact_id)` restores:

- current PNG primary;
- canonical Markdown context;
- expected PNG output path;
- artifact ID;
- expected generation;
- sanitized infographic provenance needed to preserve style.

Revision guidance:

> Revise the factual Markdown and regenerate the complete infographic using the
> artifact's resolved visual-style preset and recipe version unless the user
> explicitly requests a different visual style. Verify the revised PNG and
> Markdown together, then save with the returned artifact ID and generation.
> Do not reconstruct factual content from the pixels.

Behavior:

- ordinary content revisions do not show the preset gate again;
- an explicit request to change visual style invokes the current trusted
  visual-style preset and stores the newly selected recipe;
- if the original recipe version remains installed, use it for ordinary
  revisions;
- if the original model is unavailable, resolve the current workspace image
  model and record the change;
- every revision regenerates the full PNG;
- image-to-image editing is optional only when the resolved provider supports
  it and must not become required for correctness;
- successful save increments artifact generation and atomically replaces PNG,
  Markdown, and bounded provenance;
- failed or stale revision preserves the existing generation and files.

## 14. Failure and operational behavior

- Preset lookup or schema failure: stop before interrupt and report a bounded
  server error.
- Interrupted process restart: pending question restores from PostgreSQL
  checkpoint.
- Stale preset response: reject; never reinterpret against a newer version.
- Invalid option ID: return `422`-equivalent validation failure and keep the
  graph paused.
- User cancellation: resume with explicit cancellation and end without image
  generation.
- Resume network failure: keep selections and show retry; do not clear pending
  interrupt locally.
- Provider unavailable: return one generation failure and save nothing.
- Quota failure: use existing image-generation quota messaging and save
  nothing.
- Provider URL expiry/fetch failure: fail staging; never persist a broken URL.
- Decode/normalization failure: save nothing.
- First visual verification failure: regenerate once with consolidated
  findings.
- Persistent verification blocker: stop without save.
- Post-verification PNG or Markdown mutation: signed-receipt validation rejects
  save.
- Indexing failure: retain the verified artifact under existing retryable
  document-indexing behavior.
- Viewer failure: show the shared unviewable state and retain download.
- Unknown historical style ID: preserve artifact viewing and download; revision
  requires choosing a current style.

Observability may record:

- interrupt type, preset ID/version, and duration waiting for response;
- requested and resolved style IDs;
- image model/config ID and provider model;
- provider latency and normalized dimensions;
- generation attempt count;
- verification outcome and bounded finding categories;
- artifact ID, generation, workspace, and thread IDs under existing policy.

Do not log:

- complete source content;
- complete compiled prompts;
- provider credentials;
- base64 image data;
- temporary provider URLs;
- raw checkpoint state;
- free-text answers from future question producers.

## 15. Security and trust boundaries

- Presets are immutable trusted backend definitions.
- Browser responses contain IDs only and are validated against the pending
  checkpoint's exact preset.
- Preview assets resolve through an allowlist and cannot be arbitrary URLs.
- Question payloads are bounded before SSE serialization.
- The future `origin.kind="agent"` producer remains rejected because no such
  producer is registered in phase 12.
- The structured-question UI renders text normally and never uses
  `dangerouslySetInnerHTML`.
- Provider image URLs are fetched server-side with existing timeout and
  response-size protections; they are not persisted as primary content.
- Decoded image dimensions are checked before expensive processing.
- Sandbox output paths remain under the active workspace and cannot escape
  through traversal or symlinks.
- Artifact staging requires active infographic workflow context.
- Verification receipts bind semantic format, primary hash, Markdown hash,
  audience, and expiry.
- Public artifact access reveals no pending questions, answers, prompt recipes,
  or model credentials.

## 16. Required checks

### 16.1 Preset schemas and catalog

- `infographic.visual-style.v1` validates with one required question and five
  unique options;
- duplicate IDs, invalid defaults, unknown fields, overlong strings, excessive
  questions/options, invalid asset keys, and invalid cardinality fail;
- preset version 1 is immutable;
- all concrete styles contain complete bounded prompt directives;
- `auto` is not accepted as a concrete recipe;
- auto-resolution is deterministic for every documented signal and fallback;
- every preview asset key resolves to an app-owned asset;
- no recipe is duplicated in frontend code or the sandbox skill.

### 16.2 Interrupt and resume

- infographic instruction loading interrupts before sandbox/model/database
  side effects;
- ordinary artifact types do not trigger the visual-style preset;
- ordinary `generate_image` does not trigger it;
- interrupt SSE preserves the structured-question payload without normalizing
  it into approval actions;
- refresh and navigation restore the exact pending preset;
- valid response resumes the same checkpoint and returns the selected style;
- invalid, duplicate, unknown, stale, and wrong-version answers fail closed;
- cancel resumes and stops without provider or save calls;
- mixed approval and structured-question interrupts resume only after all are
  answered;
- existing parallel approval routing remains green;
- node re-execution does not duplicate billing, model calls, files, or rows.

### 16.3 Prompt compiler and image generation

- every concrete style contributes its expected directives;
- user facts remain unchanged across style selection;
- selected style cannot inject arbitrary frontend text;
- negative constraints and legibility requirements are always present;
- repair findings append without replacing factual requirements;
- workspace image-model resolution matches ordinary image generation;
- URL and base64 provider responses normalize to bounded PNG bytes;
- staged infographic generation creates no standalone image artifact or inline
  image result;
- normal image generation retains its existing persistence and UI behavior;
- requested/resolved style, recipe version, actual model, and dimensions are
  recorded;
- provider, quota, decode, and staging failures create no artifact.

### 16.4 Verification and persistence

- representative valid PNG + Markdown pairs verify;
- corrupt, truncated, oversized, over-dimensioned, animated, transparent,
  blank, and suspicious PNGs fail;
- malformed or oversized Markdown fails;
- visual review receives bounded factual/style context;
- missing facts, material text errors, clipping, unreadability, wrong semantic
  output, and materially absent selected style block;
- one failed review allows exactly one consolidated regeneration;
- persistent blocker never calls save;
- changing PNG or Markdown after verification rejects save;
- save creates one document, one `Artifact(format="infographic")`, one PNG
  primary, and no preview;
- no `Artifact(format="image")` sidecar is created;
- save delegates the primary to the configured artifact storage backend and
  records its backend name, immutable key, size, MIME, and checksum;
- Azure-backed tests prove one blob is written through `AzureBlobBackend`;
- local-backend tests prove the same save contract without an Azure-specific
  infographic branch;
- deleting the temporary sandbox file after save does not affect manifest,
  viewing, or download;
- provider URLs and sandbox paths never appear as durable manifest content
  URLs;
- indexing, search, citations, Git projection, deletion, and blob purge use
  ordinary artifact paths;
- revision atomically replaces PNG, Markdown, provenance, and generation.

### 16.5 Intent routing

- “create an infographic,” “visual explainer,” “process infographic,” and
  “visual comparison infographic” load the infographic skill;
- “generate an image infographic” still routes to infographic;
- illustration, photograph, icon, wallpaper, and concept-art prompts route to
  standalone image generation;
- chart, mind-map, slide-deck, PDF one-pager, HTML dashboard, and ordinary
  summary cases preserve their documented routes;
- generate-image documentation explicitly excludes infographics;
- infographic skill prohibits standalone-image persistence;
- route tests cover explicit, synonymous, ambiguous, and negative examples.

### 16.6 Frontend

- only pending `structured_question` interrupts mount above the composer;
- approval cards remain in the timeline and are not duplicated;
- default `auto` selection renders immediately;
- all five visual cards render with stable previews and labels;
- overflow arrows reflect actual horizontal overflow;
- mouse, keyboard, and touch selection work;
- selected state is not color-only;
- continue submits IDs only and cannot double-submit;
- cancel sends semantic cancellation;
- failed resume preserves pending state and selection;
- accepted resume removes the selector;
- ordinary composer submission is disabled while the graph awaits a response;
- refresh restores the selector;
- mobile uses the same component without drawer-dismiss conflicts;
- reduced motion, focus movement, live errors, and radio-group semantics pass
  accessibility checks.

### 16.7 Regression

- existing approve/edit/reject/approve-always cards and permissions remain
  unchanged;
- doom-loop and connector HITL paths remain green;
- subagent parallel interrupt routing remains green;
- ordinary image cards retain current behavior;
- PDF, DOCX, PPTX, XLSX, HTML, mindmap, flashcards, quiz, Markdown, video,
  podcast, fallback, authenticated, and public artifact behavior remain green;
- `save_artifact` remains the only completion path for infographic artifacts;
- no new infographic agent tool appears in tool metadata.

## 17. Delivery order

1. Add the immutable preset/question schemas, visual-style catalog,
   auto-resolution, and prompt-recipe tests.
2. Generalize interrupt serialization and pending state into explicit approval
   and structured-question variants while preserving every existing approval
   test.
3. Extend resume request/routing for typed structured responses, including
   checkpoint restoration, mixed interrupts, cancellation, and subagent
   routing.
4. Add the generic composer-level `StructuredQuestionPrompt`, visual-card
   presentation, responsive/accessibility behavior, and duplicate-timeline
   filtering.
5. Add infographic format identity, adapter skeleton, Markdown binding,
   manifest metadata, and focused persistence tests.
6. Extract the shared image-generation service from standalone image
   persistence without changing normal image behavior.
7. Add the backend-internal image-generation stage inside the checkpointed
   unified artifact invocation, including sandbox staging, PNG normalization,
   billing, provenance, and provider response tests without changing the
   public `generate_image` schema.
8. Add the infographic prompt compiler and one-regeneration verification loop.
9. Add `docker/sandbox/skills/infographic/SKILL.md`, intent routing,
   `load_artifact_instructions` support, roster/revision guidance, and
   standalone-image exclusions.
10. Add panel metadata/rendering, download, public access, revision, browser,
    and cross-format regression coverage.
11. Update the authoritative artifact architecture and phase status only after
    implementation satisfies the exit criteria.

Each step must leave existing chat and artifact paths functional. If the
implementation requires a new infographic save tool, a second artifact record,
an unbounded browser-authored prompt, a persisted provider URL, or treating
every PNG as an infographic, stop and repair the boundary.

## 18. Exit criteria

1. Explicit infographic intent routes to the infographic skill and never to
   standalone image generation.
2. Loading infographic instructions automatically emits the trusted
   `infographic.visual-style.v1` structured question before any billable or
   persistent work.
3. The generic question panel appears above the composer, restores after
   navigation, submits stable IDs, and supports cancellation and accessibility.
4. No agent-facing `ask_user` tool or agent-authored question content exists.
5. The response resumes the same durable LangGraph run and deterministically
   resolves one immutable visual-style recipe.
6. The selected recipe materially contributes to the model-facing infographic
   prompt and cannot be overridden by frontend text.
7. The checkpointed unified artifact invocation uses the workspace image model
   internally to generate one normalized staged PNG without calling the
   standalone `generate_image` tool or creating its artifact/card.
8. Programmatic and visual verification bind the exact PNG and searchable
   Markdown; one consolidated regeneration is the maximum repair loop.
9. Successful save creates one document-backed
   `Artifact(format="infographic")` with one PNG primary and bounded provenance.
10. Infographic and ordinary image semantics remain distinct across routing,
    tool descriptions, receipts, format metadata, manifests, viewers, and
    tests.
11. Viewing, download, public access, search, citations, revision, deletion,
    indexing, and blob lifecycle reuse the universal artifact architecture.
12. The verified PNG is persisted only by `save_artifact` through the configured
    Azure or local artifact storage backend; sandbox files and provider URLs
    are never durable output.
13. No new database model, Alembic migration, artifact API family, panel,
    citation namespace, search leg, or dedicated infographic agent tool exists.
14. Existing HITL approval flows, ordinary image generation, and every shipped
    artifact format remain green.
