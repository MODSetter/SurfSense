import type { ImageUpload } from "../api"
import type { ChatStreamEvent, NumberedEvent } from "../sse"
import { applyFrame, type LivePair } from "./apply-frame"

/** Where a run stands, as the thread list and the thinking header show it. */
export type RunState =
  { state: "queued"; position: number } | { state: "running" }

/** One thread's reply in progress, as this window follows it. */
export type LiveRun = {
  readonly threadId: number
  readonly pair: LivePair | null
  // A retried turn's ids, hidden while the reply that replaces it streams.
  readonly replaces: ReadonlyArray<number | string>
  readonly state: RunState
  readonly lastSeq: number
  readonly ended: boolean
  // What a Retry of this reply would send again, while the window holds it.
  readonly retry: { text: string; images: ImageUpload[] } | null
}

type Entry = LiveRun & { controller: AbortController }

type Listener = () => void
type EndedListener = (threadId: number) => void
type FrameListener = (threadId: number, event: ChatStreamEvent) => void

// Module level, not component state: a reply keeps arriving whichever thread
// is open, and only leaves when its stored turns have caught up.
let runs = new Map<number, Entry>()
let version = 0
const listeners = new Set<Listener>()
const endedListeners = new Set<EndedListener>()
const frameListeners = new Set<FrameListener>()

function changed() {
  version += 1
  for (const listener of [...listeners]) listener()
}

export function subscribeToRuns(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Changes whenever any run does; what `useSyncExternalStore` compares. */
export function runsVersion(): number {
  return version
}

export function liveRun(threadId: number | null): LiveRun | null {
  return threadId === null ? null : (runs.get(threadId) ?? null)
}

export function liveRuns(): LiveRun[] {
  return [...runs.values()]
}

/** Called once a run's frames end, for its thread's id. */
export function onRunEnded(listener: EndedListener): () => void {
  endedListeners.add(listener)
  return () => endedListeners.delete(listener)
}

/** Every frame, for what the pair does not hold: a title, an approval. */
export function onRunFrame(listener: FrameListener): () => void {
  frameListeners.add(listener)
  return () => frameListeners.delete(listener)
}

/** Start following a run, from a send or from a replay. */
export function beginRun(
  threadId: number,
  {
    pair = null,
    replaces = [],
    retry = null,
  }: {
    pair?: LivePair | null
    replaces?: ReadonlyArray<number | string>
    retry?: LiveRun["retry"]
  } = {}
): AbortSignal {
  runs.get(threadId)?.controller.abort()
  const controller = new AbortController()
  runs.set(threadId, {
    threadId,
    pair,
    replaces,
    state: { state: "running" },
    lastSeq: 0,
    ended: false,
    retry,
    controller,
  })
  changed()
  return controller.signal
}

/** Read a run's frames into its entry until they end, then announce it. */
export async function pump(
  threadId: number,
  frames: AsyncIterable<NumberedEvent>
): Promise<void> {
  try {
    for await (const { seq, event } of frames) {
      const entry = runs.get(threadId)
      if (!entry || entry.ended) return
      if (event.type === "done") break
      const state: RunState =
        event.type === "run-state"
          ? event.state === "queued"
            ? { state: "queued", position: event.position }
            : { state: "running" }
          : entry.state
      runs.set(threadId, {
        ...entry,
        pair: applyFrame(entry.pair, event),
        state,
        lastSeq: seq ?? entry.lastSeq,
      })
      changed()
      for (const listener of [...frameListeners]) listener(threadId, event)
    }
  } finally {
    end(threadId)
  }
}

function end(threadId: number) {
  const entry = runs.get(threadId)
  if (!entry || entry.ended) return
  runs.set(threadId, { ...entry, ended: true })
  changed()
  for (const listener of [...endedListeners]) listener(threadId)
}

/** Change the live reply in place, as a stop does before the stored turn says so. */
export function updatePair(
  threadId: number,
  change: (pair: LivePair) => LivePair
): void {
  const entry = runs.get(threadId)
  if (!entry?.pair) return
  runs.set(threadId, { ...entry, pair: change(entry.pair) })
  changed()
}

/** Stop reading a run's frames; for an agent turn, closing its stream ends it. */
export function abandonRun(threadId: number): void {
  runs.get(threadId)?.controller.abort()
}

/** Forget a run once its stored turns show the whole reply. */
export function dropRun(threadId: number): void {
  const entry = runs.get(threadId)
  if (!entry) return
  // A run that ended has nothing left to hang up on.
  if (!entry.ended) entry.controller.abort()
  runs.delete(threadId)
  changed()
}

/** For tests: every run forgotten, every listener kept. */
export function resetChatRuns(): void {
  for (const entry of runs.values()) entry.controller.abort()
  runs = new Map()
  changed()
}
