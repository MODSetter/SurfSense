# Frontend — Phase 1: Desktop dashboard

> Owns: the first authenticated-free application shell after model selection.
> API contracts are the FastAPI routes under
> `surfsense_local/backend/modules/`; there is no parallel frontend data model.
> Chat UI uses `@assistant-ui/react`.

## Goal

Open into a local-first desktop research workspace:

- a narrow workspace rail on the far left;
- a chat-thread column;
- the conversation and composer as the primary surface;
- workspace sources on the right.

The dashboard uses the generation model selected in
[`01-shell.md`](01-shell.md). The frontend displays that selection, but does
not send a model name with each chat request: the backend resolves and
validates `SelectedModel(GENERATION)` when a message is sent.

This is a desktop layout. Do not add mobile navigation, drawers, bottom bars,
touch-only variants, or mobile breakpoints.

## Layout

The requested three-column dashboard has one additional shell-level rail:

```text
┌────────┬──────────────────┬──────────────────────────────┬───────────────────┐
│ 56 px  │ Chats            │ Conversation                 │ Sources           │
│        │ 272 px           │ minmax(520 px, 1fr)          │ 320 px            │
│ WS     │ New chat         │ Thread header + model        │ Workspace files   │
│ rail   │ Thread list      │ Messages                     │ Cited in answer   │
│        │                  │ Composer                     │ Source preview    │
└────────┴──────────────────┴──────────────────────────────┴───────────────────┘
```

- The workspace rail is application navigation, not a fourth content column.
- The shell fills `100svh`; each panel owns its own vertical scrolling.
- Structural separators use shadcn `Separator` or panel borders. Do not wrap
  every region in a floating Card.
- Keep the conversation column visually quiet and widest.
- Set a desktop minimum width appropriate to the four regions. A narrow
  desktop window may compress the thread and source columns to documented
  minimums, but it does not transform into a mobile layout.
- The Electron phase should later set a matching `BrowserWindow.minWidth`;
  this browser phase must not introduce Electron APIs.

## Startup sequence

`App` is a bootstrap boundary, not the dashboard implementation.

1. Read `GET /llm/selection/generation`.
2. A `404` renders the existing model-selection screen.
3. A valid selection starts dashboard bootstrap.
4. Read `GET /workspaces`.
5. If workspaces exist, restore the last valid workspace id from the versioned
   key `surfsense-local:last-workspace:v1`; otherwise select the first workspace
   returned by the API.
6. If the list is empty, create `POST /workspaces` with
   `{"name": "My Workspace"}` and select its response.
7. Once a workspace is selected, load its threads and documents concurrently.

The create-after-empty operation is deduplicated by one module-level in-flight
promise so React Strict Mode cannot create two workspaces. The current product
assumes one renderer:

```text
ponytail: one local renderer owns bootstrap; replace this client guard with an
idempotent backend bootstrap endpoint before allowing multiple app windows.
```

If creation fails, show a retryable shell error. Do not create another
workspace until a fresh `GET /workspaces` confirms the list is still empty.

## Workspace rail

Use shadcn `Tooltip`, `Avatar`, `Button`, `DropdownMenu`, and `ScrollArea`.

- Render one item per `GET /workspaces` result.
- The visible compact mark is derived from the workspace name; its accessible
  name and tooltip contain the full name.
- The active workspace uses the sidebar semantic tokens and a static selected
  indicator. Color is not the only selected-state signal.
- Switching workspace:
  - stores the id in the versioned local-storage key;
  - clears the active thread before loading the new workspace;
  - loads threads and sources concurrently;
  - aborts stale requests and an active chat stream from the old workspace.
- A final `+` action creates another workspace using `POST /workspaces`.
- Rename and delete actions use the existing `PATCH /workspaces/{id}` and
  `DELETE /workspaces/{id}` routes. Deleting the active workspace selects the
  next remaining workspace; deleting the final workspace immediately runs the
  empty-list bootstrap again.
- Destructive deletion requires shadcn `AlertDialog`.

Do not use workspace array indexes as identities. The API's integer `id` is
the identity everywhere.

## Chat-thread column

Use shadcn `Button`, `ScrollArea`, `DropdownMenu`, `Skeleton`, and `Empty`.

- Header: active workspace name and `New chat`.
- List: `GET /workspaces/{workspace_id}/chat/threads`, already newest first.
- Each row shows its title, or `New chat` when the backend title is null.
- Thread selection loads
  `GET /chat/threads/{thread_id}/messages`.
- Delete uses `DELETE /chat/threads/{thread_id}` and removes the row only after
  success.
- Do not create an empty backend thread when `New chat` is clicked. Enter a
  local draft-thread state and create the thread on the first submitted
  message with:

```http
POST /workspaces/{workspace_id}/chat/threads
Content-Type: application/json

{"title": "<first non-empty line, at most 80 characters>"}
```

This avoids abandoned empty threads. Once creation succeeds, insert the new
thread at the top, select it, and send the pending message exactly once.

The current API has no thread rename or archive route. Do not expose actions
that imply those capabilities.

## Conversation runtime

Install the current compatible `@assistant-ui/react` package and pin its
resolved version in `pnpm-lock.yaml`.

Use:

- `AssistantRuntimeProvider`;
- `useExternalStoreRuntime`;
- `ThreadPrimitive`;
- `MessagePrimitive`;
- `ComposerPrimitive`;
- assistant-ui's official thread/message/composer components where they fit
  the repository's shadcn theme.

Do not copy the cloud application's complete chat component. It contains
authentication, tools, connectors, image capture, shared-workspace state, and
other features that are explicitly outside Community Local.

### Why `useExternalStoreRuntime`

FastAPI is already the source of truth for threads and messages. Sending a
message persists the user turn and the streamed assistant turn. A
`useLocalRuntime` history adapter would introduce a second persistence path
and risks writing the same message twice.

The dashboard owns backend message records and adapts them into assistant-ui:

```text
GET persisted messages
       │
       ▼
app-owned thread state ──convertMessage──> assistant-ui ThreadMessage
       ▲                                      │
       └────────────── onNew + SSE ───────────┘
```

The external runtime receives:

- `messages`: records for the active backend thread plus the currently
  streaming assistant draft;
- `convertMessage`: maps `MessageRead` into assistant-ui text content;
- `onNew`: extracts the submitted user text, creates a thread if necessary,
  then starts the backend message stream;
- `isRunning`: true while the SSE response is open;
- `isSendDisabled`: true without a selected model, active workspace, or
  available composer text;
- `onCancel`: aborts the active fetch.

Keep the assistant-ui runtime scoped to the active thread. Thread-list and
workspace state remain application state; assistant-ui does not become the
workspace store.

## Message streaming

Send:

```http
POST /chat/threads/{thread_id}/messages
Content-Type: application/json

{"text": "<user text>"}
```

Parse the backend's SSE frames:

```text
data: {"type":"delta","text":"..."}
data: {"type":"citations","items":[...]}
data: {"type":"error","message":"..."}
data: [DONE]
```

The parser is a small pure module with tests. It must buffer partial chunks:
one `ReadableStream` read is not guaranteed to contain one complete SSE frame.

Streaming behavior:

1. Add one optimistic user message.
2. Add one empty assistant draft.
3. Append each `delta.text` to that same draft.
4. Attach the citations frame to the assistant draft and update the source
   panel.
5. Surface an error frame inside the thread; keep any partial text.
6. On `[DONE]`, refetch `GET /chat/threads/{thread_id}/messages` and replace
   optimistic records with canonical database records and ids.

Only one run is active per renderer. Workspace/thread changes abort the prior
reader so deltas cannot leak into another thread. The backend may persist a
partial assistant turn after cancellation; the canonical refetch is
authoritative.

## Main conversation surface

- Header:
  - active thread title;
  - current model as a shadcn `Badge`;
  - provider status when unavailable.
- Empty thread:
  - concise prompt explaining that answers use the current workspace's
    sources;
  - no marketing carousel or suggested prompts in this phase.
- Messages:
  - user and assistant roles use assistant-ui message primitives;
  - assistant text uses the assistant-ui markdown renderer only if that
    dependency is deliberately added; otherwise render safe plain text;
  - citations are keyboard-focusable controls labelled with their source
    number and document title;
  - streaming, error, and stopped states remain distinguishable without
    relying only on animation.
- Composer:
  - assistant-ui composer primitives;
  - multiline input;
  - Enter sends and Shift+Enter inserts a newline;
  - send becomes stop while streaming;
  - disabled while workspace/thread bootstrap is unresolved;
  - no attachment button until source upload is implemented in the Sources
    panel.

The selected model is not duplicated in local storage and is not accepted from
composer state. `GET /llm/selection/generation` is the display value; the
backend selection row determines inference.

If message submission returns `409 no chat model selected`, return to the
model-selection gate. If the provider emits an error because a previously
selected model was removed, show the stream error and offer a path back to
model selection.

## Sources panel

The v1 Sources panel represents the active workspace, not a separate retrieval
scope. The backend currently retrieves across all ready documents in that
workspace, so do not render source-selection checkboxes.

- Load `GET /workspaces/{workspace_id}/documents` with
  `document_type=FILE&document_type=NOTE`.
- Show title, type, and status using shadcn `Badge`.
- Keep pending/processing documents visible but explain that only indexed
  content can be retrieved.
- Failed rows expose `error_message` and a Retry action using the existing
  retry endpoint.
- The header `Add` action opens a multiple-file picker and posts one
  `multipart/form-data` request to the existing upload endpoint using the
  repeated field name `files`.
- Insert the upload response's `created` documents immediately so users see
  their `pending` state without waiting for another list request. Report
  `duplicates` separately; a duplicate is not an upload failure.
- While any document is `pending` or `processing`, poll the workspace document
  list. Stop when every document is `ready` or `failed`, and abort polling when
  the workspace changes or the panel unmounts. Do not poll an idle workspace.
- The latest assistant citation frame marks documents used in the answer and
  orders those references above the full source list.
- Resolve citation `document_id` against the already loaded document list for
  its title.
- Selecting a source loads
  `GET /workspaces/{workspace_id}/documents/{document_id}` and replaces the
  list body with a back-navigable text preview.
- If citation line numbers exist, highlight or scroll to that range. If they
  are null, show the document without pretending a precise excerpt is known.

The current citation frame has `chunk_id`, `document_id`, `start_line`, and
`end_line`, but not chunk text or document title. The frontend can deliver the
document-level panel above with current APIs. A future exact chunk preview
should add one backend read contract or enrich the citation frame; it must not
issue hidden database assumptions from the frontend.

## Frontend modules

```text
src/
├── App.tsx
├── app/
│   └── app-bootstrap.tsx
├── features/
│   ├── dashboard/
│   │   └── dashboard-page.tsx
│   ├── model-selection/       # existing gate
│   ├── workspaces/
│   │   ├── api.ts
│   │   ├── use-workspaces.ts
│   │   └── workspace-rail.tsx
│   ├── chat/
│   │   ├── api.ts
│   │   ├── sse.ts
│   │   ├── use-chat-runtime.ts
│   │   ├── thread-list.tsx
│   │   ├── thread-panel.tsx
│   │   └── message.tsx
│   └── sources/
│       ├── api.ts
│       ├── use-sources.ts
│       └── sources-panel.tsx
├── components/
│   ├── assistant-ui/          # assistant-ui compositions
│   └── ui/                    # shadcn registry source only
└── lib/
    └── api.ts
```

Rules:

- API types live beside their feature; do not create a speculative universal
  domain layer.
- `dashboard-page.tsx` owns active workspace/thread identity and composes the
  panels. It does not parse SSE or perform raw fetches.
- Feature hooks own request cancellation and stale-response protection.
- Reuse `lib/api.ts` for JSON/error handling.
- Add no global state library. The shell has one owner for each selected id,
  and assistant-ui already owns chat interaction state.
- Independent workspace requests start together; dependent requests wait only
  for the id they require.

## Loading, empty, and failure behavior

- App bootstrap: full-shell skeleton with stable column geometry.
- No model: model-selection gate.
- No workspace: create once, then skeleton; never flash an empty dashboard.
- Workspace creation failure: retryable blocking Alert.
- No threads: local new-chat state with composer ready.
- Messages loading: thread skeleton while the composer stays disabled.
- No documents: Sources `Empty` with the header upload action available.
- API unavailable: blocking shell Alert with Retry.
- Provider unavailable: dashboard may render historical messages and sources,
  but sending is disabled with a direct path to model setup.
- One side-panel request failing does not erase data already loaded in the
  other panels.

## Accessibility and desktop interaction

- Workspace and thread items have visible selected, hover, focus, and disabled
  states using semantic tokens.
- Icon-only actions have accessible names and shadcn Tooltips.
- Panel regions have headings or `aria-label`s.
- Workspace rail and thread list are keyboard navigable.
- Composer follows assistant-ui keyboard behavior.
- Source citations and source rows are real buttons/links, not clickable
  `div`s.
- Focus moves to the conversation heading after switching threads and returns
  sensibly when a source preview closes.
- Streaming updates use a polite live region; errors use an assertive Alert.
- Respect reduced motion. No entrance stagger or decorative animation is
  required for this high-frequency interface.

## Acceptance

### Bootstrap and workspaces

- Fresh data directory creates exactly one `My Workspace`, even under React
  Strict Mode.
- Reload restores the last valid workspace.
- Workspace switch changes threads and sources without showing stale data from
  the prior workspace.
- Create, rename, and delete use the existing backend routes.

### Chat

- With a selected model, New chat creates no backend row until first send.
- First send creates one thread and one streamed turn.
- Reload restores the persisted thread and both messages.
- Switching threads during a stream cannot append text to the wrong thread.
- The selected model shown in the header matches
  `GET /llm/selection/generation`; the message request contains no model field.
- A missing selection returns the user to model setup.

### Sources

- Sources are scoped to the active workspace.
- Add accepts multiple files and sends them under the backend's repeated
  `files` multipart field.
- Newly uploaded files appear immediately as pending; the panel updates them
  through processing to ready or failed without a reload.
- Duplicate filenames are reported without hiding successfully created files.
- Pending, ready, and failed states are distinguishable.
- Citations from the latest answer resolve to document titles and open the
  corresponding document preview.
- No UI claims per-document retrieval selection while the backend searches the
  whole workspace.

### Quality checks

- Unit tests cover the chunk-safe SSE parser and workspace bootstrap
  deduplication.
- Component tests cover workspace switching, lazy thread creation, streaming
  deltas, citation handoff, cancellation, backend errors, multipart upload,
  and ingestion status polling.
- `pnpm test`, `pnpm typecheck`, `pnpm lint`, and `pnpm build` pass.
- Browser verification covers the full desktop layout, keyboard navigation,
  light/dark themes, long workspace/thread/document names, empty states, and a
  real FastAPI stream.

## Backend APIs used

Model:

- `GET /llm/selection/generation`
- `GET /llm/providers`

Workspaces:

- `GET /workspaces`
- `POST /workspaces`
- `PATCH /workspaces/{workspace_id}`
- `DELETE /workspaces/{workspace_id}`

Threads and messages:

- `GET /workspaces/{workspace_id}/chat/threads`
- `POST /workspaces/{workspace_id}/chat/threads`
- `GET /chat/threads/{thread_id}/messages`
- `POST /chat/threads/{thread_id}/messages`
- `DELETE /chat/threads/{thread_id}`

Sources:

- `GET /workspaces/{workspace_id}/documents`
- `GET /workspaces/{workspace_id}/documents/{document_id}`
- `POST /workspaces/{workspace_id}/documents/upload`
- `POST /workspaces/{workspace_id}/documents/{document_id}/retry`

## Out of scope

- Mobile UI.
- Electron window controls and native menus.
- Thread rename/archive until backend routes exist.
- Per-document retrieval selection until backend query scope supports it.
- Tools, connectors, web search, image generation, voice, collaboration, auth,
  and cloud sync.
- Copying the cloud dashboard wholesale.
