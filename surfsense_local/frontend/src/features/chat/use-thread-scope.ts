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

// The threads this client opened for a new chat. A tick made while one was
// opening is for it, and for no other chat that took its place meanwhile.
const openedForNewChat = new Set<number>()

/** Called once a new chat's thread exists and is the chat on screen. */
export function threadOpenedForNewChat(threadId: number) {
  openedForNewChat.add(threadId)
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
 * ticks it started with. A new chat shows the ticks the workspace remembers,
 * and its ticks are remembered in turn; a thread's never are. The thread a
 * new chat opens is created with the ticks on screen, and a tick made while
 * it is opening is stored on that thread alone. If that thread never takes
 * the screen, the tick stays with the new chat's ticks instead.
 */
export function useThreadScope({
  workspaceId,
  view,
  activeThread,
  sourceScope,
  scopeEdits,
  setSourceScope,
  keepScopeForChat,
  rememberShownScope,
  showRememberedScope,
}: {
  workspaceId: number
  view: ConversationView
  activeThread: ChatThread | null
  sourceScope: SourceScope
  /** Counts the user's own ticks, never a scope this hook put on screen. */
  scopeEdits: number
  /** Puts a thread's stored ticks on screen. */
  setSourceScope: (scope: SourceScope) => void
  /** Leaves the ticks on screen to a chat: the workspace stops remembering them. */
  keepScopeForChat: () => void
  /** Hands the ticks on screen back to the workspace, which remembers them. */
  rememberShownScope: () => void
  /** Puts the workspace's remembered ticks on screen, for a new chat. */
  showRememberedScope: () => void
}) {
  const queryClient = useQueryClient()
  const threadId = view.status === "active" ? view.threadId : null
  // The chat whose ticks are on screen; a thread not in the list yet waits.
  const shown = useRef<{ workspaceId: number; threadId: number | null } | null>(
    null
  )
  const seenEdits = useRef(scopeEdits)
  // The workspace whose new chat is opening its thread, if one is.
  const opening = useRef<number | null>(null)

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
    if (view.status === "creating") {
      // The ticks on screen are on their way to the thread being opened.
      opening.current = workspaceId
      keepScopeForChat()
      return
    }
    const wasOpening = opening.current === workspaceId
    opening.current = null
    const current = shown.current
    if (threadId === null) {
      if (wasOpening) {
        // No thread opened: the ticks, with any made meanwhile, are the new
        // chat's again.
        seenEdits.current = scopeEdits
        rememberShownScope()
      } else if (
        current?.workspaceId !== workspaceId ||
        current.threadId !== null
      ) {
        showRememberedScope()
      }
      shown.current = { workspaceId, threadId }
      return
    }
    if (current?.workspaceId === workspaceId && current.threadId === threadId) {
      return
    }
    if (wasOpening && !openedForNewChat.has(threadId)) {
      // Another chat took the place of the thread that was opening: a tick
      // made meanwhile stays with the new chat's ticks, and is not this chat's.
      seenEdits.current = scopeEdits
      rememberShownScope()
    }
    if (activeThread === null) {
      // A tick made before the thread's entry arrives is the thread's.
      keepScopeForChat()
      return
    }
    openedForNewChat.delete(threadId)
    shown.current = { workspaceId, threadId }
    if (scopeEdits !== seenEdits.current) {
      // Ticks made while the thread's entry was still on its way, or while
      // the thread was being opened for a new chat, are the user's for this
      // thread: they stay, and the thread gets them.
      seenEdits.current = scopeEdits
      keepScopeForChat()
      storeWhenIdle(threadId, sourceScope)
    } else {
      const waiting = heldScopes.get(threadId)
      if (waiting !== undefined) {
        setSourceScope(waiting)
      } else if (activeThread.source_scope !== undefined) {
        setSourceScope(activeThread.source_scope ?? EVERY_SOURCE)
      } else {
        // An entry without a scope was made by this client: the ticks on
        // screen opened it, and stay.
        keepScopeForChat()
      }
    }
  })

  useEffect(() => {
    if (scopeEdits === seenEdits.current) return
    // A tick made while a new chat's thread is being opened is for that
    // thread: it stays unseen until the thread opens.
    if (view.status === "creating") return
    const current = shown.current
    if (current?.workspaceId !== workspaceId || current.threadId !== threadId) {
      return
    }
    seenEdits.current = scopeEdits
    // A new chat's ticks are the workspace's, which remembers them itself.
    if (threadId !== null) storeWhenIdle(threadId, sourceScope)
  })
}
