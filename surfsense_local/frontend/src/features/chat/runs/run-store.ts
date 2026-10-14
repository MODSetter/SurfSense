import type { ImageUpload } from "../api"
import type { ChatStreamEvent, NumberedEvent } from "../sse"
import { applyFrame, type LivePair } from "./apply-frame"

/** Where a run stands, as the thread list and the thinking header show it. */
export type RunState =
  | { state: "queued"; position: number }
  | { state: "running" }
  // The agent asked the user something and does nothing until it is answered.
  | { state: "needs-approval" }

/** One thread's reply in progress, as this window follows it. */
export type LiveRun = {
  readonly threadId: number
  // Runs outlive a switch of workspace, so each says whose thread it is.
  readonly workspaceId: number
  readonly pair: LivePair | null
  // A retried turn's ids, hidden while the reply that replaces it streams.
  readonly replaces: ReadonlyArray<number | string>
  readonly state: RunState
  readonly lastSeq: number
  readonly ended: boolean
  // What a Retry of this reply would send again, while the window holds it.
  readonly retry: { text: string; images: ImageUpload[] } | null
}

/** A run as the page outside its thread reads it: everything but the reply. */
export type RunSummary = {
  readonly state: RunState
  readonly ended: boolean
  // A replayed run has no pair until its `accepted` frame.
  readonly hasPair: boolean
}

type Entry = Omit<LiveRun, "lastSeq"> & {
  lastSeq: number
  controller: AbortController
}

type Listener = () => void
type EndedListener = (threadId: number) => void
type FrameListener = (threadId: number, event: ChatStreamEvent) => void

const NO_RUNS: Readonly<Record<number, RunSummary>> = {}

// Module level, not component state: a reply keeps arriving whichever thread
// is open, and only leaves when its stored turns have caught up.
let runs = new Map<number, Entry>()
let summaries = NO_RUNS
const listeners = new Set<Listener>()
const endedListeners = new Set<EndedListener>()
const frameListeners = new Set<FrameListener>()
let pendingNotice: ReturnType<typeof setTimeout> | null = null
let lastNotice = Number.NEGATIVE_INFINITY

// Text is told at most this often: each render reads the whole live reply, so
// a fast model on a long reply would otherwise keep the window busy redrawing.
export const TEXT_NOTICE_GAP_MS = 32

/** Tell every subscriber now, of this change and of frames not yet told. */
function notify() {
  if (pendingNotice !== null) {
    clearTimeout(pendingNotice)
    pendingNotice = null
  }
  lastNotice = performance.now()
  for (const listener of [...listeners]) listener()
}

// The frames of one network read are applied in microtasks, before any
// timer runs, so one notice a macrotask later renders them all at once, and
// none comes sooner than TEXT_NOTICE_GAP_MS after the last. Not an animation
// frame: a hidden window gets none, and its replies still stream.
function notifySoon() {
  pendingNotice ??= setTimeout(
    notify,
    Math.max(0, lastNotice + TEXT_NOTICE_GAP_MS - performance.now())
  )
}

function sameState(a: RunState, b: RunState) {
  return a.state === "queued"
    ? b.state === "queued" && a.position === b.position
    : a.state === b.state
}

/** Brings one thread's summary in line, keeping the object while it holds. */
function summarize(threadId: number) {
  const entry = runs.get(threadId)
  const previous = summaries[threadId]
  if (!entry) {
    if (!previous) return
    const rest = { ...summaries }
    delete rest[threadId]
    summaries = rest
    return
  }
  const hasPair = entry.pair !== null
  if (
    previous?.ended === entry.ended &&
    previous.hasPair === hasPair &&
    sameState(previous.state, entry.state)
  ) {
    return
  }
  summaries = {
    ...summaries,
    [threadId]: { state: entry.state, ended: entry.ended, hasPair },
  }
}

export function subscribeToRuns(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/**
 * Every run's summary, by thread. The same object until a run starts, ends,
 * changes state or gets its pair, so a reader sits out the frames of text.
 */
export function runSummaries(): Readonly<Record<number, RunSummary>> {
  return summaries
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
    workspaceId,
    pair = null,
    replaces = [],
    retry = null,
  }: {
    workspaceId: number
    pair?: LivePair | null
    replaces?: ReadonlyArray<number | string>
    retry?: LiveRun["retry"]
  }
): AbortSignal {
  runs.get(threadId)?.controller.abort()
  const controller = new AbortController()
  runs.set(threadId, {
    threadId,
    workspaceId,
    pair,
    replaces,
    state: { state: "running" },
    lastSeq: 0,
    ended: false,
    retry,
    controller,
  })
  summarize(threadId)
  notify()
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
            : { state: event.state }
          : entry.state
      const pair = applyFrame(entry.pair, event)
      if (pair === entry.pair && sameState(state, entry.state)) {
        // A title or an approval changes nothing the run shows; only the
        // number moves, and no one is told.
        entry.lastSeq = seq ?? entry.lastSeq
      } else {
        runs.set(threadId, {
          ...entry,
          pair,
          state,
          lastSeq: seq ?? entry.lastSeq,
        })
        summarize(threadId)
        notifySoon()
      }
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
  summarize(threadId)
  // At once, with any frames still waiting, before anyone hears it ended.
  notify()
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
  notify()
}

/** Forget a run once its stored turns show the whole reply. */
export function dropRun(threadId: number): void {
  const entry = runs.get(threadId)
  if (!entry) return
  // A run that ended has nothing left to hang up on.
  if (!entry.ended) entry.controller.abort()
  runs.delete(threadId)
  summarize(threadId)
  notify()
}

/** For tests: every run forgotten, every listener kept. */
export function resetChatRuns(): void {
  for (const entry of runs.values()) entry.controller.abort()
  runs = new Map()
  summaries = NO_RUNS
  notify()
}
