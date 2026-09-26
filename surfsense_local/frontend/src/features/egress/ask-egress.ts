import { useEffect, useSyncExternalStore } from "react"

/**
 * The questions waiting on the egress prompt. Refused requests
 * (`setEgressPrompt` in `lib/api`) and `askEgress` both queue here, outside
 * the prompt, which remounts wherever the innermost open dialog is.
 */

export type Pending = {
  destination: string
  host: string
  // What Allow does. A refused request enables the destination and is retried;
  // the updater talks to GitHub from Electron, so its consent is a pref there.
  allow: () => Promise<unknown>
  resolve: (allowed: boolean) => void
}

// The first question stays shown after it is answered, until the prompt has
// finished closing (`advanceEgressQueue`).
let state: { queue: Pending[]; answered: boolean } = {
  queue: [],
  answered: false,
}
let prompts = 0
const listeners = new Set<() => void>()

function publish(next: typeof state) {
  state = next
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => void listeners.delete(listener)
}

/**
 * Ask outside a refused request: either because none can raise the question,
 * the call not being the backend's to make, or because the answer is wanted
 * before the request rather than after it, where a refusal would otherwise be
 * the user's first news that a feature is off.
 *
 * Resolves false when the prompt is not mounted, so a caller outside the app
 * shell simply gets no consent rather than an error.
 */
export function askEgress(request: Omit<Pending, "resolve">): Promise<boolean> {
  if (prompts === 0) return Promise.resolve(false)
  return new Promise((resolve) =>
    publish({ ...state, queue: [...state.queue, { ...request, resolve }] })
  )
}

export function settleEgress(allowed: boolean) {
  if (state.answered || !state.queue[0]) return
  state.queue[0].resolve(allowed)
  publish({ ...state, answered: true })
}

export function advanceEgressQueue() {
  if (!state.answered) return
  publish({ queue: state.queue.slice(1), answered: false })
}

// The question a mounted prompt shows, and whether it is still waiting.
export function useEgressQuestion() {
  useEffect(() => {
    prompts += 1
    // A prompt that moved mid-close never reports the close finishing.
    advanceEgressQueue()
    return () => {
      prompts -= 1
      // After the commit, so moving to another dialog is not an unmount.
      queueMicrotask(() => {
        if (prompts > 0) return
        state.queue.forEach((pending) => pending.resolve(false))
        publish({ queue: [], answered: false })
      })
    }
  }, [])
  const { queue, answered } = useSyncExternalStore(subscribe, () => state)
  return { question: queue[0], open: queue[0] !== undefined && !answered }
}
