import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { errorToast } from "@/features/feedback/error-toast"
import type { SourceScope } from "@/features/sources/tree/scope-state"
import { intl } from "@/i18n/intl"

import { type ChatThread, storeThreadScope } from "./api"
import { chatKeys } from "./query-keys"
import { onRunEnded, runSummaries } from "./runs/run-store"
import type { ConversationView } from "./use-chat-runtime"

const EVERY_SOURCE: SourceScope = {
  all: true,
  folder_ids: [],
  excluded_folder_ids: [],
  document_ids: [],
  excluded_document_ids: [],
}

function draftKey(workspaceId: number) {
  return `surfsense:draft-scope:${workspaceId}:v1`
}

const isIdList = (value: unknown): value is number[] =>
  Array.isArray(value) && value.every((id) => typeof id === "number")

/** The ticks a new chat kept, or null for none it can read. */
export function readDraftScope(workspaceId: number): SourceScope | null {
  try {
    const raw = localStorage.getItem(draftKey(workspaceId))
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== "object" || parsed === null) return null
    const scope = parsed as Record<string, unknown>
    if (
      typeof scope.all !== "boolean" ||
      !isIdList(scope.folder_ids) ||
      !isIdList(scope.excluded_folder_ids) ||
      !isIdList(scope.document_ids) ||
      !isIdList(scope.excluded_document_ids)
    ) {
      return null
    }
    return {
      all: scope.all,
      folder_ids: scope.folder_ids,
      excluded_folder_ids: scope.excluded_folder_ids,
      document_ids: scope.document_ids,
      excluded_document_ids: scope.excluded_document_ids,
    }
  } catch {
    return null
  }
}

function writeDraftScope(workspaceId: number, scope: SourceScope | null) {
  try {
    if (scope === null) localStorage.removeItem(draftKey(workspaceId))
    else localStorage.setItem(draftKey(workspaceId), JSON.stringify(scope))
  } catch {
    // Storage refused; the draft lives for the session only.
  }
}

/**
 * The draft is spent once a thread has been opened with its ticks. A tick made
 * while that thread was opening is not in the draft: it waits for the thread
 * ([useThreadScope]), and a genuinely newer chat ends the opening before the
 * draft is spent.
 */
export function clearDraftScope(workspaceId: number) {
  writeDraftScope(workspaceId, null)
}

// A run outlives the page, so what waits on it lives here, not in a hook: the
// ticks held while a thread's reply runs, and the order of a thread's stores.
const stores = new Map<number, Promise<void>>()
const heldScopes = new Map<number, SourceScope>()
// Each mounted page keeps its threads cache in step with what is stored.
const cacheWriters = new Set<(threadId: number, scope: SourceScope) => void>()

// Each thread's stores run one after another, so an older one cannot land
// after a newer one and leave the thread with ticks the user has changed.
function queueStore(threadId: number, scope: SourceScope) {
  for (const write of cacheWriters) write(threadId, scope)
  const previous = stores.get(threadId) ?? Promise.resolve()
  const pending = previous
    .then(() => storeThreadScope(threadId, scope))
    .then(
      () => undefined,
      () => {
        // The next turn sends the ticks anyway; until then the thread
        // would open with its earlier ticks after a reload.
        errorToast(
          intl.formatMessage({
            id: "chat_scope_save_error",
            defaultMessage: "Couldn’t save which sources this chat uses",
          }),
          {
            description: intl.formatMessage({
              id: "chat_scope_save_body",
              defaultMessage: "They go with your next message anyway.",
            }),
          }
        )
      }
    )
  stores.set(threadId, pending)
  void pending.then(() => {
    if (stores.get(threadId) === pending) stores.delete(threadId)
  })
}

/**
 * Stores now, or once the thread's reply has ended: the agent's tools read
 * the stored scope on every call, and a turn keeps the ticks it started with.
 */
function storeWhenIdle(threadId: number, scope: SourceScope) {
  const run = runSummaries()[threadId]
  if (run !== undefined && !run.ended) heldScopes.set(threadId, scope)
  else queueStore(threadId, scope)
}

onRunEnded((threadId) => {
  const scope = heldScopes.get(threadId)
  if (scope === undefined) return
  heldScopes.delete(threadId)
  queueStore(threadId, scope)
})

/**
 * Keeps the sources panel's ticks with the chat they belong to. Opening a
 * thread puts its stored scope on screen; a tick made in it between turns is
 * stored at once, so the thread shows it again when it is opened next. A tick
 * made while the thread's reply runs is held and stored once the reply ends:
 * the agent's tools read the stored scope on every call, and a turn keeps the
 * ticks it started with. A new chat keeps its ticks as a draft across a
 * reload, until the chat is sent: the thread is opened with them, and the
 * draft is spent; a tick made while that thread is opening waits for it.
 */
export function useThreadScope({
  workspaceId,
  view,
  activeThread,
  sourceScope,
  scopeEdits,
  setSourceScope,
}: {
  workspaceId: number
  view: ConversationView
  activeThread: ChatThread | null
  sourceScope: SourceScope
  /** Counts the user's own ticks, never a scope this hook put on screen. */
  scopeEdits: number
  setSourceScope: (scope: SourceScope) => void
}) {
  const queryClient = useQueryClient()
  const threadId = view.status === "active" ? view.threadId : null
  // The chat whose ticks are on screen; a thread not in the list yet waits.
  const shown = useRef<{ workspaceId: number; threadId: number | null } | null>(
    null
  )
  const seenEdits = useRef(scopeEdits)

  // Keeps the thread's cached entry in step with each store, so reopening the
  // thread shows the ticks before the list is read again.
  useEffect(() => {
    const write = (threadId: number, scope: SourceScope) => {
      queryClient.setQueryData<ChatThread[]>(
        chatKeys.threads(workspaceId),
        (threads) =>
          threads?.map((thread) =>
            thread.id === threadId ? { ...thread, source_scope: scope } : thread
          )
      )
    }
    cacheWriters.add(write)
    return () => {
      cacheWriters.delete(write)
    }
  }, [queryClient, workspaceId])

  useEffect(() => {
    const current = shown.current
    if (current?.workspaceId === workspaceId && current.threadId === threadId) {
      return
    }
    if (threadId === null) {
      setSourceScope(readDraftScope(workspaceId) ?? EVERY_SOURCE)
      shown.current = { workspaceId, threadId }
      return
    }
    if (activeThread === null) return
    shown.current = { workspaceId, threadId }
    if (scopeEdits !== seenEdits.current) {
      // Ticks made while the thread's entry was still on its way, or while
      // the thread was being opened for a new chat, are the user's for this
      // thread: they stay, and the thread gets them.
      seenEdits.current = scopeEdits
      storeWhenIdle(threadId, sourceScope)
    } else {
      const waiting = heldScopes.get(threadId)
      if (waiting !== undefined) {
        setSourceScope(waiting)
      } else if (activeThread.source_scope !== undefined) {
        setSourceScope(activeThread.source_scope ?? EVERY_SOURCE)
      }
    }
    // An entry without a scope was made by this client: the ticks on screen
    // opened it, and stay.
  })

  useEffect(() => {
    if (scopeEdits === seenEdits.current) return
    // A tick made while a new chat's thread is being opened is for that
    // thread, not the draft: it stays unseen until the thread opens.
    if (view.status === "creating") return
    const current = shown.current
    if (current?.workspaceId !== workspaceId || current.threadId !== threadId) {
      return
    }
    seenEdits.current = scopeEdits
    if (threadId === null) writeDraftScope(workspaceId, sourceScope)
    else storeWhenIdle(threadId, sourceScope)
  })
}
