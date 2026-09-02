# Phase 8 — Interactive Flashcard Artifacts

**Status:** Planned.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 1 artifact persistence and manifests, phase 3 signed verification receipts, phase 5 programmatic-verification precedent, phase 6 artifact drawer, and phase 7 format-level viewer dispatch.
**Independent of:** phase 10 public access. Phase 8 ships authenticated generation, study, progress persistence, revision, and download. Public viewing is phase 10 work.

## 1. Goal

Add generated flashcard decks as first-class artifacts through the universal
artifact flow:

```text
load_artifact_instructions("flashcards")
  -> execute
  -> verify_artifact(path=..., format="flashcards")
  -> save_artifact(path=...)
```

A flashcard artifact:

- stores one strict JSON deck as its primary file;
- derives searchable Markdown from the verified JSON in trusted backend code;
- renders through one interactive viewer in the desktop artifact panel and the
  existing mobile Vaul drawer;
- supports reveal, previous/next, remembered, missed, progress counts, and
  review-missed;
- persists only the latest remembered/missed mark for each card in the existing
  `Artifact.metadata` JSONB column;
- downloads the canonical JSON deck;
- uses programmatic verification only, with no conversion, preview, screenshot,
  rasterization, or vision-model review.

This phase adds one format adapter, one generation skill, one format-aware
viewer, and one artifact-scoped progress mutation. It does not add another
artifact model, agent tool, streaming path, panel, mobile viewer, database
table, database column, Alembic migration, scheduler, or review-history log.

## 2. Product and scope decisions

### 2.1 JSON is the canonical artifact

The strict deck is JSON because flashcards are ordered structured records, not
a free-form document. Standard JSON parsing plus an exact schema gives the
backend and frontend a smaller, more reliable contract than a custom Markdown
grammar.

The agent authors the values probabilistically, but it does not decide what
constitutes a valid flashcard format. The skill explains the contract;
`verify_artifact` enforces it before any bytes can be persisted. An invalid
deck receives actionable findings and no signed receipt.

`Document.source_markdown` remains required by the artifact architecture, but
it is a deterministic projection of the verified primary JSON. It is not a
second agent-authored source of truth and is never parsed to render the deck.

### 2.2 Initial study profile

Phase 8 supports:

- front and back Markdown strings;
- an optional hint Markdown string;
- one ordered deck;
- reveal by pointer, Space, or Enter;
- previous and next navigation;
- binary self-grading: `good` and `again`;
- remembered, missed, and unseen counts;
- a review containing only cards currently marked `again`;
- shared artifact-level progress across authenticated sessions.

Phase 8 intentionally does not support:

- FSRS, SM-2, due dates, retention targets, or adaptive scheduling;
- Hard/Easy ratings, immutable review events, streaks, or study analytics;
- per-user progress or private marks in a shared workspace;
- persisted card order, shuffle order, current index, or flipped side;
- multiple-choice, cloze, reversible, typed, or sibling cards;
- embedded images, audio, video, HTML, remote resources, or active links;
- card editing, deletion, insertion, or reordering in the viewer;
- the NotebookLM-style Explain action;
- public progress mutation;
- a dedicated `save_flashcards` or `create_flashcards` agent tool.

These exclusions are load-bearing. If personalized progress, review history, or
adaptive scheduling becomes real, it requires a user-scoped persistence design
instead of extending the shared artifact metadata map.

### 2.3 Renderer choice

Use the already-installed `motion` package behind a local
`FlashcardSurface`. Motion owns only presentation:

- controlled front/back rotation;
- card-change entrance/exit treatment if retained after usability testing;
- reduced-motion behavior.

SurfSense owns parsing, navigation, grading, persistence, controls,
accessibility, and responsive layout. Do not add `react-quizlet-flashcard`,
`react-card-flip`, or another deck-state package.

## 3. Persistence and format identity

A flashcard deck is:

- one `Document(document_type=ARTIFACT)` containing derived searchable
  Markdown;
- one `Artifact(format="flashcards")`;
- one primary `<slug>.json` `ArtifactFile` with MIME `application/json`;
- no preview file.

`ArtifactFormat` may add `FLASHCARDS = "flashcards"` for typed callers and
roster clarity. The database column remains a string. No Alembic migration is
required.

The primary JSON owns deck semantics and download bytes. The document Markdown
owns indexing, search, citations, Git projection, and agent revision context.
The projection is generated from the exact verified primary bytes during save,
so these representations cannot be authored independently.

Physical `.json` and `application/json` identify the file representation.
Explicit `format="flashcards"` in the verification receipt, artifact row,
manifest, and viewer dispatch identifies its semantics. A generic JSON file
must never acquire flashcard behavior from its suffix or MIME alone.

## 4. Canonical JSON contract

Version 1 has this complete shape:

```json
{
  "schema_version": 1,
  "title": "Calculus fundamentals",
  "cards": [
    {
      "front_markdown": "What is a **limit**?",
      "back_markdown": "The value a function approaches as its input approaches another value.",
      "hint_markdown": "Think about approaching rather than necessarily reaching."
    },
    {
      "front_markdown": "What does a derivative represent?",
      "back_markdown": "An instantaneous rate of change."
    }
  ]
}
```

The schema is closed:

- the top level contains exactly `schema_version`, `title`, and `cards`;
- `schema_version` is the integer `1`;
- `title` is a non-empty string;
- `cards` is a non-empty ordered array;
- every card contains exactly `front_markdown`, `back_markdown`, and optionally
  `hint_markdown`;
- front and back are non-empty strings;
- hint is omitted when absent, not serialized as an unrelated sentinel;
- unknown fields fail verification.

Card identity within one immutable generation is its zero-based array index.
Progress is generation-scoped and resets on revision, so persistent card IDs
would add structure without preserving any required behavior.

### 4.1 Bounds

Keep limits in one backend module and mirror them in the generation skill and
frontend schemas:

- 2–100 cards;
- title at most 200 Unicode code points;
- front at most 4,000 code points;
- back at most 12,000 code points;
- hint at most 2,000 code points;
- existing `ARTIFACT_MAX_FILE_BYTES` limit for the complete JSON file;
- existing frontend pre-fetch and post-fetch byte checks.

The verifier normalizes only for checks; it does not silently rewrite agent
bytes. It rejects:

- invalid UTF-8, a byte-order mark, or control characters outside ordinary
  JSON whitespace;
- duplicate object keys;
- non-object top levels;
- non-integer or unsupported schema versions;
- missing, extra, null, boolean, numeric, object, or array values where strings
  are required;
- empty values after trimming;
- out-of-range card counts or field lengths;
- raw HTML, images, active links, and other unsupported Markdown constructs;
- duplicate fronts after Unicode normalization, whitespace collapsing, and
  case folding.

Duplicate-front detection is a bounded quality guard, not semantic
deduplication. The verifier does not claim that differently worded cards test
different concepts.

### 4.2 What verification cannot prove

Programmatic verification proves that the deck is structurally valid, bounded,
safe to render, and compatible with the viewer. It cannot prove that an answer
is factually correct, that the cards cover the source material, or that the
difficulty is pedagogically appropriate.

Those are content-quality properties of agent generation. Phase 8 does not add
a second LLM review disguised as format verification.

## 5. Programmatic verification

Add `verification/formats/flashcards.py` with
`check_flashcards_json(data: bytes) -> StructuralCheckResult`, and register:

```python
FormatAdapter(
    name="flashcards",
    suffix=".json",
    mime_type="application/json",
    convert_to_pdf=False,
    check=check_flashcards_json,
    requires_visual_review=False,
)
```

Add `"flashcards"` to `VerifiableArtifactFormat`. A successful verification:

- runs no LibreOffice command;
- creates no PDF;
- rasterizes no pages;
- calls no vision LLM;
- creates no preview;
- signs the exact primary SHA-256;
- records `visual="not_required"`;
- reports non-sensitive notes such as card count and schema version.

Use the standard library JSON decoder with an object-pairs hook that rejects
duplicate keys, then validate the parsed value through a closed Pydantic model
with `extra="forbid"`. Do not add a JSON Schema runtime or another validation
dependency.

The existing signed-receipt boundary remains authoritative:

1. verify reads and checks the JSON;
2. the receipt binds the exact accepted primary hash;
3. save reads the file again and rejects post-verification mutation;
4. only those exact bytes become the primary artifact file.

No canonical whitespace or object-key ordering is required. JSON semantics,
not pretty-print style, define validity.

## 6. Trusted Markdown projection

The agent must not independently summarize the JSON into
`markdown_representation`, because an unrelated summary could drift from the
deck while still passing primary-file verification.

Extend `FormatAdapter` with one optional pure capability:

```python
markdown_projection: Callable[[bytes], str] | None = None
```

The flashcards adapter sets:

```python
markdown_projection=flashcards_to_markdown
```

`flashcards_to_markdown` parses through the same validated deck model and emits:

```markdown
# Calculus fundamentals

## Card 1

### Front

What is a **limit**?

### Back

The value a function approaches as its input approaches another value.

### Hint

Think about approaching rather than necessarily reaching.
```

For adapters with `markdown_projection`, the existing `save_artifact` tool:

1. validates the signed receipt and reads the receipt-bound primary;
2. derives Markdown from those exact bytes;
3. ignores no caller-supplied alternative: the public tool contract omits
   `markdown_representation` for projection-backed formats;
4. passes the derived Markdown to the existing format-blind persistence
   service.

For Markdown-only and every existing binary adapter without a projection,
`markdown_representation` remains required exactly as today. This is a
capability on the universal adapter/save mechanism, not a flashcards-specific
agent tool or persistence branch.

Projection is deterministic and pure. Unit tests require identical Markdown
for identical parsed JSON, normalized final newline, escaped structural
headings where necessary, and no raw JSON dump in the searchable document.

## 7. Generation skill and intent routing

Add `docker/sandbox/skills/flashcards/SKILL.md` and advertise
`"flashcards"` through `load_artifact_instructions`.

The skill teaches the agent to:

1. identify the concepts the user needs to recall;
2. write one deliverable-named JSON file under `/workspace`;
3. use the exact closed schema and stay within field/card limits;
4. keep each front atomic and each back sufficient but concise;
5. call `verify_artifact(path=..., format="flashcards")`;
6. repair all blocking findings in one pass and reverify once;
7. call the existing `save_artifact` with the verified path and title;
8. stop with an explanation after a persistent blocker.

The skill is authoring guidance, not the trust boundary. A malformed file is
rejected even when the skill was loaded, and a valid file can be verified
without trusting how it was produced.

Intent routing adds flashcards ahead of PDF and HTML defaults. Explicit
requests for flashcards, study cards, revision cards, memorization cards, or a
deck to practice recall select `flashcards`. A request to explain or summarize
a topic remains a document. A multiple-choice quiz is not silently converted
to flashcards.

Update:

- deliverables `system_prompt.md`;
- deliverables `description.md`;
- `tools/sandbox.py` format literal;
- installed-skill roster tests;
- routing tests covering explicit, synonymous, and negative intent.

No new tool registration, activity kind, completion emitter, or frontend tool
card is introduced. Generation still ends through `save_artifact`.

## 8. Manifest and download contract

The ordinary authenticated manifest retains its shared fields and adds
format-scoped flashcard data only when `format == "flashcards"`:

```json
{
  "artifact_id": 123,
  "format": "flashcards",
  "generation": 1,
  "markdown_representation": "# Calculus fundamentals\n...",
  "files": [
    {
      "role": "primary",
      "filename": "calculus-flashcards.json",
      "mime_type": "application/json",
      "content_url": "/api/v1/workspaces/7/artifacts/123/files/456/content"
    }
  ],
  "flashcard_progress": {
    "generation": 1,
    "marks": {
      "0": "good",
      "1": "again"
    }
  }
}
```

Do not expose raw `Artifact.metadata`. Build a sanitized progress response that
accepts only the current generation, integer-like indexes in range, and
`good`/`again` values. Malformed legacy metadata degrades to empty progress and
logs a warning without making the deck unviewable.

The primary content route remains attachment-only for `application/json` with
`X-Content-Type-Options: nosniff`. The stable download route returns the exact
primary JSON under a safe `.json` filename. No CSV, Markdown, Anki package, or
PDF export is added.

The manifest ETag must vary when sanitized progress changes. Include a
deterministic digest of current-generation marks in addition to document
content hash and artifact generation. Do not increment artifact generation for
a study mark.

## 9. Progress persistence

Use the existing `Artifact.metadata` JSONB:

```json
{
  "flashcards": {
    "progress": {
      "generation": 1,
      "marks": {
        "0": "good",
        "1": "again"
      }
    }
  }
}
```

This state is intentionally:

- shared by all authenticated collaborators who can update the artifact;
- one latest mark per card, not a review log;
- scoped to the exact artifact generation;
- absent for unseen cards;
- reset completely whenever a revision increments generation.

Current index, front/back state, temporary review-missed order, and loading
state stay local to the viewer. On open, select the first unseen card; if every
card is marked, select the first card. This resumes useful work without
persisting another session object.

### 9.1 Mutation route

Add:

```text
PATCH /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/flashcard-progress
```

Request:

```json
{
  "generation": 1,
  "card_index": 0,
  "mark": "good"
}
```

`mark` is `good`, `again`, or `null`; `null` returns the card to unseen.

The route:

1. requires `ARTIFACTS_UPDATE`;
2. loads and row-locks the workspace-scoped artifact;
3. rejects a non-flashcards format with `404`;
4. compares the supplied generation and returns `409` when stale;
5. reads the bounded primary JSON and parses it through the shared validator;
6. rejects an out-of-range card index with `422`;
7. replaces only the target entry in a copied marks map;
8. discards marks from another generation or outside the current card range;
9. commits atomically and returns sanitized progress.

Do not use a generic arbitrary-metadata patch route. Clients may mutate only
this bounded namespace and cannot write verification, legacy, media, or other
artifact metadata.

Progress writes must not:

- replace primary bytes or file rows;
- update the document body, hash, path, or indexing status;
- increment artifact generation;
- create a Git commit or indexing run;
- overwrite unrelated artifact metadata;
- make the artifact appear content-revised in the library.

If SQLAlchemy's `updated_at` default would mark a progress write as a content
revision, explicitly preserve its existing value in this mutation. ETag
variation comes from the progress digest, not the content timestamp.

### 9.2 Concurrency

The row lock serializes shared marks. Two updates to different card indexes
merge against the latest map. Two updates to the same card are last-committed
write wins. The response is authoritative; the frontend reconciles its
optimistic cache with it.

Phase 8 does not claim multi-user learning semantics. If two collaborators
study the same deck, they deliberately share and overwrite one progress map.

## 10. Right-panel renderer

### 10.1 Format-level dispatch

`application/json` is not sufficient to select flashcard behavior. Extend
`artifact-viewer-dispatch.ts` ahead of MIME dispatch:

```text
manifest.format == "flashcards"
  -> FlashcardsViewer
otherwise
  -> existing format/MIME/no-primary behavior
```

Add format metadata:

- icon: a card-stack or layers icon already available in `lucide-react`;
- label: `Interactive`;
- detail label: `Flashcards`;
- group: `Files`;
- viewing mode: `viewer`.

The chat save card and artifact collection already carry
`format="flashcards"` and require no new rendering path.

### 10.2 Loading and parsing

`FlashcardsViewer` is a client-only dynamic import. Until all of the following
are complete, render only the existing
`@/components/ui/spinner` centered in the available panel:

1. primary metadata is available;
2. primary JSON bytes have been fetched;
3. the response has passed pre-fetch and post-fetch size checks;
4. UTF-8 decoding and Zod validation have succeeded;
5. current-generation progress has been normalized;
6. initial card selection has been calculated.

Do not mount the card shell, Motion faces, progress controls, or measured card
layout during this state. Showing a partially sized or one-faced card creates
the deformed loading state this requirement exists to prevent.

The loading container uses `aria-busy="true"` and an accessible loading label.
Fetch, decode, or parse failure replaces the spinner with the shared
`UnviewableFile` state while preserving the header download action.

Frontend Zod mirrors the backend closed schema and limits as defense in depth.
It does not accept unknown versions or try to repair malformed decks.

### 10.3 Motion surface

Create a local `FlashcardSurface` owned by the feature. It receives:

- rendered front content;
- rendered back content;
- `revealed`;
- reveal callback;
- reduced-motion preference.

Use `motion.div` for a controlled `rotateY` transition. The host supplies CSS
perspective; the inner surface uses `transform-style: preserve-3d`; each face
uses `backface-visibility: hidden`; the back face starts at `rotateY(180deg)`.

The default transition is short and non-springy enough to preserve legibility.
Do not add tilt, glare, parallax, card physics, swipe grading, or decorative
stack animation.

Use `useReducedMotion`. For reduced-motion users, do not freeze the transform
at the front face: render the selected face directly or use an opacity-only
swap. Both faces must never remain exposed to the accessibility tree at once.

The surface is not the state machine. It contains no card index, progress
mutation, fetch, or deck logic and can be replaced without changing viewer
behavior.

### 10.4 Study behavior

- A new card starts on its front.
- Clicking/tapping the card or pressing Space/Enter reveals its back.
- Tick (`good`) and cross (`again`) are disabled until the back is revealed.
- Tick/cross optimistically update progress, then advance to the next card.
- A failed mutation rolls back the mark and does not silently report success.
- Previous/next changes cards without grading and resets to the front.
- Existing marks are visible and can be changed after reveal.
- Counts derive from the latest marks: remembered, missed, unseen.
- `Review missed` creates a local ordered view of current `again` indexes.
- Completing review-missed returns to the ordinary deck summary.

No automatic timer grades or advances a card.

### 10.5 Accessibility and mobile

Use actual buttons for reveal and controls. Visible labels or tooltips expose
`Remembered`, `Needs review`, `Previous card`, and `Next card`; icons and
green/red colors are not the only signal.

The hidden face has `aria-hidden`; focus never enters hidden content. Announce
card position, answer reveal, mark result, and completion through bounded
status text. Keyboard shortcuts ignore events from interactive descendants.

Mobile mounts the same viewer through `MobileArtifactDrawer`. Put
`data-vaul-no-drag` on the card and control region so taps and horizontal
pointer movement do not dismiss the drawer. The viewer owns internal vertical
scrolling for long content and never creates a nested Vaul drawer.

## 11. Revision

`load_artifact_for_revision(artifact_id)` restores:

- the current `.json` primary;
- derived Markdown context;
- a `.json` expected output path;
- current `artifact_id` and `expected_generation`.

Add a `flashcards` revision instruction:

> Edit the restored JSON deck without changing its schema version, verify the
> revised JSON, and save it with the returned artifact ID and generation. Do
> not edit the derived Markdown or reconstruct the deck with vision.

Revision follows the ordinary receipt and optimistic-generation contract.
After the primary and derived Markdown are replaced atomically, clear
`metadata.flashcards.progress` for the new generation in the same transaction.
A failed or stale revision preserves the current primary, Markdown, generation,
and marks.

## 12. Failure and operational behavior

- Invalid JSON/schema/content: verification returns all bounded actionable
  findings possible in one pass and issues no receipt.
- Vision service unavailable: irrelevant; flashcards never enter that path.
- Post-verification file mutation: save rejects the primary hash mismatch.
- Projection failure: save fails before persistence; never store JSON without
  its searchable Markdown.
- Indexing failure: retain the saved JSON and artifact under the existing
  retryable document-status behavior.
- Viewer fetch/parse failure: show shared fallback and preserve JSON download.
- Progress read corruption: use empty sanitized progress and log metadata keys,
  never user card content.
- Progress write failure: rollback optimistic UI and retain the current card.
- Stale generation: return `409`, invalidate manifest, and load the new deck.

Logs may include artifact ID, generation, schema version, card count, operation,
duration, and failure category. Do not log fronts, backs, hints, or the full
progress map.

## 13. Required checks

### 13.1 Schema and verification

- representative valid decks, including Unicode and supported Markdown, pass;
- invalid UTF-8, BOM, duplicate keys, unknown top-level/card fields, wrong
  types, unsupported schema versions, empty values, bad counts, excessive
  lengths, control characters, unsupported Markdown, and duplicate fronts fail;
- valid verification records `visual="not_required"` and no rendered fields;
- no conversion, rasterization, preview, or vision call occurs;
- changed bytes after verification cannot save;
- a generic `.json` never receives flashcard verification without explicit
  `format="flashcards"`.

### 13.2 Projection and persistence

- validated JSON projects to stable readable Markdown;
- caller-supplied Markdown cannot override the projection;
- save creates one document, one `Artifact(format="flashcards")`, one
  `application/json` primary, and no preview;
- JSON, derived Markdown, format, and receipt hash refer to the same accepted
  primary;
- indexing/search/citations use derived Markdown through the ordinary document
  path;
- download returns exact JSON bytes under a safe filename;
- revision replaces JSON and projection atomically, increments generation,
  resets marks, and purges the superseded blob.

### 13.3 Progress

- current-generation `good`, `again`, and `null` updates succeed;
- stale generation returns `409`;
- wrong format, workspace, artifact, permission, and card index fail closed;
- updates preserve unrelated metadata and content timestamps;
- concurrent different-card writes merge under the row lock;
- manifest sanitizes malformed marks and varies its ETag after a valid update;
- progress writes do not increment generation, reindex, write Git, or replace
  artifact files;
- revision resets marks only after the new generation commits.

### 13.4 Frontend

- format-level dispatch wins over generic `application/json` MIME behavior;
- the shared Spinner is the only card-body loading UI until fetch, validation,
  progress normalization, and initial selection complete;
- no deformed card shell or Motion face mounts during loading;
- invalid/oversized data shows the shared fallback with download preserved;
- reveal, previous/next, tick/cross, optimistic rollback, counts, first-unseen
  selection, and review-missed follow the specified state transitions;
- hidden faces stay out of the accessibility tree;
- reduced motion uses an instant or opacity face swap, not a frozen 3D card;
- mobile interaction does not drag-dismiss the Vaul drawer;
- desktop and mobile render the same component and state behavior.

### 13.5 Routing and regression

- explicit and synonymous study-card prompts load the flashcards skill;
- summary, document, quiz, mind-map, and interactive-calculator prompts retain
  their existing routes;
- roster and revision instructions advertise flashcards;
- `save_artifact` remains the only save tool and completion-emission path;
- PDF, DOCX, PPTX, XLSX, HTML, mindmap, Markdown, media, and fallback-format
  behavior remain green.

## 14. Delivery order

1. Add the closed Pydantic deck model, strict JSON decoder, duplicate-front
   normalization, Markdown projection, and focused fixtures.
2. Add the flashcards adapter, format registration, no-vision verification,
   primary hash receipt, and post-verification mutation checks.
3. Add adapter-owned Markdown projection to the universal save path and prove
   every existing format retains its current `markdown_representation`
   contract.
4. Add the sandbox skill, intent routing, roster entry, revision instruction,
   and one execute-to-verify-to-save integration.
5. Add format-level dispatch, dynamic viewer, shared-Spinner loading gate,
   Zod validation, Motion surface, controls, accessibility, and desktop/mobile
   tests.
6. Add sanitized manifest progress, ETag variation, bounded PATCH mutation,
   optimistic frontend updates, rollback, and concurrency coverage.
7. Add revision-time progress reset, cross-format regression, and authoritative
   plan updates.

Each step leaves one universal artifact path. If implementation requires a new
agent save tool, artifact table, file role, search leg, citation kind, panel
state, or mobile viewer, stop and repair the adapter/viewer boundary.

## 15. Exit criteria

1. Flashcard intent generates a strict version-1 JSON deck through the existing
   execute tool and saves only after programmatic verification.
2. Verification is deterministic, signed, primary-hash-bound, and never calls
   conversion, rasterization, preview generation, or a vision LLM.
3. The exact verified JSON is the primary download and the only semantic source
   of the trusted backend-generated searchable Markdown.
4. Save, revision, blob lifecycle, indexing, search, citations, chat cards, and
   completion streaming remain the universal artifact mechanisms.
5. The authenticated panel and Vaul drawer use one lazy viewer with a Motion
   surface, accessible controls, and the shared Spinner as the complete
   pre-render loading state.
6. Reveal, navigation, remembered/missed marking, counts, first-unseen resume,
   and review-missed work without FSRS or another deck-state package.
7. Tick/cross marks persist only in existing artifact metadata, do not trigger
   content revision/indexing, and reset atomically on artifact revision.
8. No Alembic migration, new persistence model, separate agent tool, vision
   review, public progress mutation, or Explain action exists.
9. Existing formats and phase 10 public/fallback assumptions remain green.
