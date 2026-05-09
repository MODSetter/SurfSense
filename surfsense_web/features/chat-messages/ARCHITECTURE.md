# `features/chat-messages/` — Architecture

> **Scope.** This module owns everything between an assistant message
> arriving and its rendering inside the chat UI: the timeline (the
> agent's process — reasoning + every tool call), and the HITL
> primitives that per-tool components compose to render approval views.
>
> It does **NOT** own: the thread shell, the composer, the streaming
> pipeline, the message frame (`assistant-message.tsx`,
> `user-message.tsx`, markdown renderer, citations), the comments
> sidebar, or any of the 63 individual tool-ui integration files
> under `components/tool-ui/`.

---

## 1. Mental model

Every assistant message has two regions:

| Region | What it shows |
|---|---|
| **Timeline** | The agent's *process*. Reasoning, every tool call, grouped by delegation `spanId` into a tree. Each tool call is rendered by its registered component, which selects its own view (running, awaiting approval, success, error, etc.) by discriminating its `result` data. |
| **Body** | The agent's *product*. Markdown text, citations, native reasoning blocks, and value-add deliverables (image viewer, chart, canvas). Connector tool cards do NOT render here. |

**Principle: timeline = process, body = product. No overlap.**

A tool's UI lives in the body **if and only if** it produces a deliverable
the user wants to interact with — view, scrub, copy, share. If the UI
just shows that the tool ran and what it did, it lives in the timeline.

```
┌─ Assistant Message ─────────────────────────────────────────┐
│                                                             │
│  ╔═════════════════════════════════════════════════════╗   │
│  ║  TIMELINE  (process)                                ║   │
│  ║                                                     ║   │
│  ║  ▸ task: NotionAgent              [running]         ║   │
│  ║      ▸ search_workspace           [completed]       ║   │
│  ║      ▸ update_page                ← rendered by     ║   │
│  ║          (Notion-styled approval     UpdateNotion-  ║   │
│  ║           card OR Notion-styled      PageToolUI;    ║   │
│  ║           success/error card,        the component  ║   │
│  ║           per its own data           picks the view ║   │
│  ║           discrimination)            from result)   ║   │
│  ║  ▸ summarize                      [completed]       ║   │
│  ╚═════════════════════════════════════════════════════╝   │
│                                                             │
│  ╔═════════════════════════════════════════════════════╗   │
│  ║  BODY  (product)                                    ║   │
│  ║                                                     ║   │
│  ║  Markdown text, citations, value-add deliverables   ║   │
│  ║  only. Connector tool cards do NOT render here.     ║   │
│  ╚═════════════════════════════════════════════════════╝   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. The single data model

The timeline reads ONE data structure: a `TimelineItem[]`. There are
no parallel structures for "thinking steps", "tool calls", "HITL
bundles", etc. Every visible piece of agent activity is a `TimelineItem`.

### 2.1 The discriminated union (outer discrimination)

Two kinds. The timeline does **outer discrimination** — it chooses
reasoning view vs tool-call mounting based on `kind`.

```ts
type ItemStatus =
    | "pending" | "running" | "completed" | "cancelled" | "error";

interface BaseItem {
    id: string;
    spanId?: string;             // groups items into delegation tree (parent task + children)
    status: ItemStatus;
}

interface ReasoningItem extends BaseItem {
    kind: "reasoning";
    text: string;
}

interface ToolCallItem extends BaseItem {
    kind: "tool-call";
    toolName: string;
    args: Record<string, unknown>;
    argsText?: string;
    result?: unknown;            // per-tool component discriminates this internally
    langchainToolCallId?: string;
}

type TimelineItem = ReasoningItem | ToolCallItem;

interface TimelineGroup {
    parent: TimelineItem;
    children: TimelineItem[];
}
```

**`ToolCallItem` has no `approval` field, no `phase`, no `view`.** All of
that is derived inside the per-tool component from the result data.

### 2.2 Inner discrimination (per-tool component)

Each tool registers a component that receives the tool-call data and
decides what to render based on its own result-shape discriminators:

```tsx
const UpdateNotionPageToolUI: TimelineToolComponent = (props) => {
    if (isInterruptResult(props.result))    return <NotionApprovalCard {...props} />;
    if (isAuthErrorResult(props.result))    return <NotionAuthErrorCard {...props} />;
    if (isErrorResult(props.result))        return <NotionErrorCard {...props} />;
    if (isInfoResult(props.result))         return <NotionNotFoundCard {...props} />;
    if (isSuccessResult(props.result))      return <NotionSuccessCard {...props} />;
    return <NotionPendingCard {...props} />;
};
```

The discriminators (`isInterruptResult`, `isAuthErrorResult`, etc.)
are **types, not centralized infrastructure**. The component owns
the dispatch. The timeline knows none of this.

### 2.3 The pure builder

```ts
function buildTimeline(
    content: MessageContent[],
    thinkingSteps: ThinkingStep[],
): TimelineGroup[]
```

Builds the timeline from existing message content + thinking-step data
parts. Pure function. Sets `kind` and `status` on each item; preserves
`result` verbatim for per-tool discrimination.

### 2.4 The dispatch (timeline-level)

Two cases. Exhaustive switch. No runtime guards in the timeline renderer.

```tsx
function TimelineItemView({ item }: { item: TimelineItem }) {
    switch (item.kind) {
        case "reasoning": return <ReasoningItemView item={item} />;
        case "tool-call": return <ToolCallItemView item={item} />;
    }
}

function ToolCallItemView({ item }: { item: ToolCallItem }) {
    const ToolBody = getToolComponent(item.toolName) ?? FallbackToolBody;
    return <ToolBody {...adaptItemToProps(item)} />;
}
```

**No card frame, header, body slot, approval area, or result panel
at the timeline level.** Each tool component owns its own visual
presentation. This matches how every existing tool-ui component
already works — they each render their own rounded card with their
own header.

---

## 3. The timeline's tool-component contract

Tool components mounted by the timeline implement a subset of
assistant-ui's `ToolCallMessagePartProps` — only the fields the
timeline can supply:

```ts
interface TimelineToolProps {
    toolCallId: string;
    toolName: string;
    args: Record<string, unknown>;
    argsText?: string;
    result?: unknown;
    langchainToolCallId?: string;
    status: ItemStatus;          // simple enum, not assistant-ui's complex status object
}

type TimelineToolComponent = (props: TimelineToolProps) => ReactNode;
```

Notably absent (compared to `ToolCallMessagePartProps`):
- `addResult`, `resume` — runtime-only, not needed; HITL decisions
  flow through `useHitlDecision` (a hook) which talks to the runtime
  directly.
- The complex `status: ToolCallMessagePartState["status"]` object —
  replaced by our simple `ItemStatus` enum.

The 15 existing HITL-aware tool-ui components only use the subset
above. They are **retyped** to `TimelineToolComponent` in the cutover
commit (mechanical: `ToolCallMessagePartComponent` → `TimelineToolComponent`).

---

## 4. Rendering topology — how the body opts out

The body uses assistant-ui's `MessagePrimitive.Parts` and registers a
**no-op fallback** for tool calls so they don't render here:

```tsx
<MessagePrimitive.Parts
    components={{
        Text: MarkdownText,
        Reasoning,
        Source,
    }}
    tools={{
        by_name: BODY_TOOLS,         // value-add deliverables only (image viewer, etc.)
        fallback: () => null,         // every other tool-call: render nothing in the body
    }}
/>
```

`BODY_TOOLS` starts empty (no value-add deliverables exist yet) and
grows as we identify them. Every tool not in `BODY_TOOLS` renders
nothing in the body.

The timeline reads message content via `useAuiState(({ message }) =>
message?.content)` and runs `buildTimeline` to produce the items it
renders. Tool-call data IS in the message; the body just chooses not
to render it.

**Result:** zero dual placement. Zero suppression HOC. Zero
render-target context. Zero coordination.

---

## 5. Slice layout

```
features/chat-messages/
├── ARCHITECTURE.md
│
├── timeline/                                ← the process surface
│   ├── types.ts                             (TimelineItem union, ToolCallItem, ItemStatus, TimelineGroup)
│   ├── build-timeline.ts                    (pure: content + thinkingSteps → groups)
│   ├── grouping.ts                          (pure: group items by spanId)
│   ├── subagent-rename.ts                   (pure: parent task title from args.subagent_type)
│   ├── tool-registry/                       (PRIVATE to timeline; only timeline mounts tools)
│   │   ├── types.ts                         (TimelineToolComponent, TimelineToolProps)
│   │   ├── registry.ts                      (TOOLS_BY_NAME from components/tool-ui/*)
│   │   ├── adapt-props.ts                   (pure: ToolCallItem → TimelineToolProps)
│   │   ├── fallback/
│   │   │   ├── fallback-tool-body.tsx       (TimelineToolComponent for unregistered tools — discriminates internally)
│   │   │   ├── default-fallback-card.tsx    (the non-HITL fallback view: status icon + collapsible + JSON)
│   │   │   ├── revert-button.tsx            (revert affordance — used by default-fallback-card)
│   │   │   ├── use-tool-action.ts           (action lookup hook for revert)
│   │   │   └── index.ts
│   │   └── index.ts
│   ├── items/
│   │   ├── reasoning-item.tsx               (renders kind: "reasoning")
│   │   ├── tool-call-item.tsx               (lookup component + mount with adapted props — ~10 lines)
│   │   └── index.ts
│   ├── timeline.tsx                         (groups + iteration + 2-case dispatch)
│   ├── data-renderer.tsx                    (assistant-ui adapter; exports TimelineDataUI)
│   └── index.ts
│
├── hitl/                                    ← pure HITL primitives
│   ├── types.ts                             (InterruptResult, HitlPhase, HitlDecision, isInterruptResult)
│   ├── use-hitl-decision.ts                 (hook: dispatch approve/edit/reject — used by every approval card)
│   ├── use-hitl-phase.ts                    (hook: tracks pending → processing → approved/rejected/edited)
│   ├── approval-cards/                      (the FALLBACK-mounted approval views; per-tool components import from here OR build their own)
│   │   ├── generic-approval.tsx             (default approval UI — what FallbackToolBody mounts for interrupt results)
│   │   ├── doom-loop-approval.tsx           (special-case approval UI + isDoomLoopInterrupt)
│   │   └── index.ts
│   ├── edit-panel/
│   │   ├── edit-panel.atom.ts               (Jotai atoms for the panel state)
│   │   ├── edit-panel.tsx                   (root: atom wiring + desktop/mobile switch only)
│   │   ├── fields/
│   │   │   ├── email-tags-field.tsx         (EmailsTagField + parse/format helpers)
│   │   │   ├── calendar-field.tsx           (DateTimePickerField + parse/format helpers)
│   │   │   ├── extra-fields.tsx             (ExtraField switch renderer)
│   │   │   └── index.ts                     (private barrel)
│   │   └── index.ts
│   └── index.ts
│
└── (no body slice yet — body just registers `tools={{ fallback: () => null }}`)
```

### 5.1 Notable absences

| Was | Status | Reason |
|---|---|---|
| `tool-cards/` slice | **Folded into `timeline/`** | Tool-call rendering happens in the timeline; the tool-registry is private to timeline. |
| `bundleTool` composer | **Deleted** | Body opts out via `fallback: () => null`. No HOCs to compose. |
| `withDelegationSpanIndent` HOC | **Deleted** | Tree indent is owned by the timeline's group renderer. |
| `withBundleStep` + `HitlBundleProvider` | **Deleted** | Multi-approval is just N inline renderings; no coordination needed. |
| `withHitlInTimeline` + `HitlRenderTargetProvider` | **Deleted** | Tool cards never render in body; no dual-placement to suppress. |
| `pickApprovalCard` central dispatcher | **Deleted** | Each tool component picks its own view via internal discrimination. The fallback has its OWN internal dispatcher (interrupt → generic-approval; doom-loop → doom-loop-approval). |
| `getHitlToolComponent` registry | **Deleted** | The tool-registry is just a `Record<string, TimelineToolComponent>`; lookup is `TOOLS_BY_NAME[name]`. |
| Centralized `approval-area.tsx` in timeline | **Deleted** | The approval is a view the per-tool component renders, not an area the timeline composes. |
| `ApprovalState` on `ToolCallItem` | **Deleted** | Phase is local UI state inside per-tool approval cards (via `useHitlPhase`). The timeline doesn't track it. |
| `ThinkingStepToolInfoMap` Map join | **Deleted** | The unified `TimelineItem` union eliminates the join. |

---

## 6. Public surfaces

### `timeline/index.ts`

```ts
export { TimelineDataUI };               // the assistant-ui registration
export { Timeline };                     // exposed for tests
export type { TimelineItem, ReasoningItem, ToolCallItem, TimelineGroup, ItemStatus };
export type { TimelineToolComponent, TimelineToolProps };
```

### `hitl/index.ts`

```ts
export type { InterruptResult, InterruptActionRequest, InterruptReviewConfig, HitlDecision, HitlPhase };
export { isInterruptResult };

export { useHitlDecision };
export { useHitlPhase };

export { GenericHitlApprovalToolUI };    // for tool-ui integrations that want to compose on top
export { DoomLoopApprovalToolUI, isDoomLoopInterrupt };

export { HitlEditPanel, MobileHitlEditPanel };
export { openHitlEditPanelAtom, closeHitlEditPanelAtom, hitlEditPanelAtom };
export type { ExtraField };
```

The 63 `components/tool-ui/*` integrations consume `hitl/`'s public
surface (types, hooks, edit-panel atom, optionally the fallback
approval cards). Nothing else.

---

## 7. Layering & SRP rules

### 7.1 The "what knows about what" rule

| Component | Knows about |
|---|---|
| `timeline/` | Itself + `hitl/` (via the fallback) + `components/tool-ui/*` (via the registry) |
| `timeline/tool-registry/` | The `TimelineToolComponent` contract, `components/tool-ui/*`, and `hitl/` (for the fallback's approval views) |
| `hitl/` | Itself only — no knowledge of timeline, tool-call types, registry |
| `components/tool-ui/*` | `hitl/` only (for HITL primitives + optional fallback approval cards); never reaches into `timeline/` |
| Body (`assistant-message.tsx`) | The `BODY_TOOLS` registry and `TimelineDataUI` from `timeline/index.ts` |

`hitl/` does **NOT** import from `timeline/`. The dependency arrow is one-way.

### 7.2 Render policy belongs to the surface, not the primitive

- `hitl/` exposes hooks, types, and the fallback approval cards.
- `timeline/` decides WHEN and WHERE tool components mount (inside
  `tool-call-item.tsx`).
- A `hitl/` primitive must never assume it's being rendered in the
  timeline, the body, or anywhere else. It receives props, renders
  UI, returns. No environment sniffing, no context.
- Per-tool components in `components/tool-ui/*` decide WHICH view to
  render based on result-shape discriminators. The timeline does not
  know these discriminators exist.

### 7.3 Single Responsibility

Rules in priority order:

1. **One responsibility per file.** Need "and" to describe it? Split it.
2. **One responsibility per function.** Same.
3. **Line count is a smell, not a budget.** ~250 lines = pause and
   ask "still one responsibility?"; ~500 lines = strong presumption
   of split needed unless explicitly justified at the top of the file.

Notable splits driven by SRP during the port:

- `hitl-edit-panel.tsx` (current 405 lines, 4 responsibilities) → 5
  files: `edit-panel.tsx` (root + layout switch), `email-tags-field.tsx`,
  `calendar-field.tsx`, `extra-fields.tsx`, `edit-panel.atom.ts`.
- `tool-fallback.tsx` (current 533 lines, 3 responsibilities) → split
  across `fallback-tool-body.tsx`, `default-fallback-card.tsx`,
  `revert-button.tsx`, `use-tool-action.ts`.
- `thinking-steps.tsx` (current 434 lines, 5 responsibilities) →
  folded into the new `timeline/` slice across `types.ts`,
  `build-timeline.ts`, `grouping.ts`, `subagent-rename.ts`,
  `timeline.tsx`, `items/*`, `data-renderer.tsx`.

---

## 8. Tested behaviors

Unit tests live next to the file they cover (`*.test.ts(x)`).

- `timeline/build-timeline.test.ts` — content + thinkingSteps → correct items, correct kind, correct status, correct ordering. `result` preserved verbatim.
- `timeline/grouping.test.ts` — items group correctly by spanId; first item with a spanId is the parent; orphaned children are promoted defensively.
- `timeline/subagent-rename.test.ts` — `task` step's display title resolves to `args.subagent_type` (title-cased); falls back to "Task" when subagent type is missing.
- `timeline/tool-registry/registry.test.ts` — `TOOLS_BY_NAME` includes every named tool; `FallbackToolBody` is returned for unknown names; the fallback dispatches correctly (interrupt → generic, doom-loop → doom-loop, otherwise → default fallback).
- `timeline/tool-registry/adapt-props.test.ts` — `ToolCallItem` → `TimelineToolProps` mapping is lossless; status mapping is correct.
- `hitl/use-hitl-phase.test.ts` — phase transitions through pending → processing → approved/rejected/edited correctly.
- `hitl/approval-cards/doom-loop-approval.test.tsx` — `isDoomLoopInterrupt` matches doom-loop-shape interrupts only.

Smoke test after cutover:
- Assistant message renders; markdown + citations work in body.
- All connector tool calls render in timeline only (none in body).
- Reasoning steps render in timeline.
- Single HITL flow (Notion update): approve, edit, reject — each transitions through the phases correctly.
- Multiple pending HITL cards: each renders inline at its position; deciding one doesn't affect the others.
- Doom-loop approval renders the special card.
- Revert button works on completed default-fallback cards and survives reload.
- Subagent name renaming on `task` parent step.

---

## 9. Migration plan (strangler fig, single atomic cutover)

### Phase A — Build the new slice in parallel

In dependency order: `hitl/` first (leaf), then `timeline/`. The
existing code (`thinking-steps.tsx`, `tool-fallback.tsx`,
`assistant-message.tsx`'s tool registry, etc.) remains fully
functional throughout Phase A.

1. Port `hitl/` primitives. Apply SRP splits (edit panel into 5 files).
   `hitl/approval-cards/{generic,doom-loop}-approval.tsx` are ported
   as standalone components — they're what the fallback mounts and
   what per-tool integrations may compose on top of.
2. Build `timeline/` slice. Implement `buildTimeline` from scratch
   (do NOT copy thinking-steps logic verbatim — design the pure
   function around the new union). Build the `tool-registry/` with
   `TimelineToolComponent` contract; the registry imports from
   `components/tool-ui/*` (no file moves yet).
3. Add unit tests as listed in §8.
4. Verify: tsc clean, biome clean, no consumer file touched, no
   linter regressions.

### Phase B — Atomic cutover (single commit)

| File | Change |
|---|---|
| `components/assistant-ui/assistant-message.tsx` | Replace `TOOLS_BY_NAME`/`TOOLS_FALLBACK` definitions with `BODY_TOOLS` (initially empty) + `tools={{ fallback: () => null }}`. Replace `ThinkingStepsDataUI` registration with `TimelineDataUI`. |
| `components/public-chat/public-thread.tsx` | Same registry + data UI swap. |
| `app/dashboard/.../new-chat/page.tsx` | Switch `ThinkingStepsDataUI` → `TimelineDataUI`. Drop `HitlBundleProvider` (no longer needed). |
| `components/free-chat/free-chat-page.tsx` | Switch `ThinkingStepsDataUI` → `TimelineDataUI`. |
| `components/public-chat/public-chat-view.tsx` | Same. |
| `components/layout/ui/right-panel/RightPanel.tsx` | Switch `HitlEditPanel` import to `@/features/chat-messages/hitl`. |
| The 15 `components/tool-ui/*` HITL-aware integration files | (a) Switch HITL imports from `@/lib/hitl`, `@/hooks/use-hitl-phase`, `@/atoms/chat/hitl-edit-panel.atom` → `@/features/chat-messages/hitl`. (b) Retype from `ToolCallMessagePartComponent` → `TimelineToolComponent` (mechanical type rename). |

### Phase C — Delete legacy

After cutover passes smoke tests:

- `components/assistant-ui/thinking-steps.tsx`
- `components/assistant-ui/tool-fallback.tsx`
- `lib/chat/delegation-span-indent.ts`
- `lib/hitl/` (entire folder)
- `components/hitl-bundle-pager/` (entire folder)
- `components/tool-ui/generic-hitl-approval.tsx`
- `components/tool-ui/doom-loop-approval.tsx`
- `components/hitl-edit-panel/` (entire folder)
- `hooks/use-hitl-phase.ts`
- `atoms/chat/hitl-edit-panel.atom.ts`

Verify: no orphan files, no dead imports, no test regressions.

---

## 10. Out of scope (and one consumer relationship)

### 10.1 The 63 `components/tool-ui/*` integrations

These are **first-class consumers** of `hitl/` and the
`TimelineToolComponent` contract. They are imported by
`timeline/tool-registry/registry.ts` to build `TOOLS_BY_NAME`. They
never reach into `timeline/` themselves.

They stay where they are. Future option to move them is a separate,
mechanical follow-up refactor.

### 10.2 Not touched by this refactor

- The composer (input bar, mention picker, prompt picker, tool toggles).
- The streaming pipeline (`lib/chat/streaming-state.ts`, `stream-pipeline.ts`, `thread-persistence.ts`).
- The chat-comments sidebar.
- The message frame (`assistant-message.tsx`, `user-message.tsx`, `markdown-text.tsx`, `inline-citation.tsx`) beyond swapping the registry imports.

If any of these become a blocker for the refactor (e.g. the streaming
pipeline needs a metadata field that doesn't exist), surface it
explicitly and decide whether to expand scope before touching it.
