import { followWorkspaceEvents } from "./api"

export type WorkspaceChangeKind =
  "documents" | "artifacts" | "chat-runs" | "folders"

/** Which rows changed and to what; absent when a dropped stream came back. */
export type WorkspaceChange = { ids: number[]; status: string }

type Listener = (change?: WorkspaceChange) => void

type Subscription = {
  controller: AbortController
  listeners: Map<WorkspaceChangeKind, Set<Listener>>
}

const FIRST_RETRY_MS = 1_000
const LAST_RETRY_MS = 10_000

// One stream per workspace, however many lists listen to it.
const subscriptions = new Map<number, Subscription>()

function wait(milliseconds: number, signal: AbortSignal) {
  if (signal.aborted) return Promise.resolve()
  return new Promise<void>((resolve) => {
    const onAbort = () => {
      window.clearTimeout(timeout)
      resolve()
    }
    const timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort)
      resolve()
    }, milliseconds)
    signal.addEventListener("abort", onAbort, { once: true })
  })
}

function notify(
  listeners: Iterable<Listener> | undefined,
  change?: WorkspaceChange
) {
  for (const listener of [...(listeners ?? [])]) listener(change)
}

async function follow(workspaceId: number, subscription: Subscription) {
  const { signal } = subscription.controller
  let retry = FIRST_RETRY_MS
  let listenedBefore = false
  while (!signal.aborted) {
    try {
      for await (const event of followWorkspaceEvents(workspaceId, signal)) {
        if (event.type === "connected") {
          retry = FIRST_RETRY_MS
          // The first connection needs no reload: mounting just loaded the lists.
          if (listenedBefore) {
            for (const listeners of subscription.listeners.values()) {
              notify(listeners)
            }
          }
          listenedBefore = true
        } else {
          notify(subscription.listeners.get(event.type), {
            ids: event.ids,
            status: event.status,
          })
        }
      }
    } catch {
      // Dropped or refused: the lists still work, and the loop tries again.
    }
    await wait(retry, signal)
    retry = Math.min(retry * 2, LAST_RETRY_MS)
  }
}

/**
 * Calls `listener` when the workspace's rows of this kind change by another
 * hand: a plugin, a second window, the worker. Also after a dropped stream is
 * back, for whatever changed while nothing was listening. Returns the
 * unsubscribe; the stream closes with its last listener.
 */
export function subscribeToWorkspaceChanges(
  workspaceId: number,
  kind: WorkspaceChangeKind,
  listener: Listener
) {
  let subscription = subscriptions.get(workspaceId)
  if (!subscription) {
    subscription = { controller: new AbortController(), listeners: new Map() }
    subscriptions.set(workspaceId, subscription)
    void follow(workspaceId, subscription)
  }
  const current = subscription
  const listeners = current.listeners.get(kind) ?? new Set<Listener>()
  current.listeners.set(kind, listeners)
  listeners.add(listener)

  return () => {
    listeners.delete(listener)
    if ([...current.listeners.values()].every((set) => set.size === 0)) {
      current.controller.abort()
      if (subscriptions.get(workspaceId) === current) {
        subscriptions.delete(workspaceId)
      }
    }
  }
}
