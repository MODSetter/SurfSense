import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { errorToast } from "@/features/feedback/error-toast"
import type { SourceScope } from "@/features/sources/tree/scope-state"
import { intl } from "@/i18n/intl"

import { type ChatThread, storeThreadScope } from "./api"
import { chatKeys } from "./query-keys"
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

/** The draft as stored, to tell later whether it changed meanwhile. */
export function draftScopeSnapshot(workspaceId: number): string | null {
  try {
    return localStorage.getItem(draftKey(workspaceId))
  } catch {
    return null
  }
}

/**
 * The draft is spent once a thread has been opened with its ticks. Given the
 * snapshot taken when that started, a draft written since, for a newer chat,
 * is left alone.
 */
export function clearDraftScope(workspaceId: number, snapshot?: string | null) {
  if (snapshot !== undefined && draftScopeSnapshot(workspaceId) !== snapshot) {
    return
  }
  writeDraftScope(workspaceId, null)
}

/**
 * Keeps the sources panel's ticks with the chat they belong to. Opening a
 * thread puts its stored scope on screen; a tick made in it between turns is
 * stored at once, so the thread shows it again when it is opened next. A new
 * chat keeps its ticks as a draft across a reload, until the chat is sent:
 * the thread is opened with them, and the draft is spent.
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
  // Each thread's stores run one after another, so an older one cannot land
  // after a newer one and leave the thread with ticks the user has changed.
  const stores = useRef(new Map<number, Promise<void>>())

  // Keeps the thread's cached entry in step, so reopening it shows the ticks
  // before the list is read again, and stores them.
  const store = (threadId: number, scope: SourceScope) => {
    queryClient.setQueryData<ChatThread[]>(
      chatKeys.threads(workspaceId),
      (threads) =>
        threads?.map((thread) =>
          thread.id === threadId ? { ...thread, source_scope: scope } : thread
        )
    )
    const previous = stores.current.get(threadId) ?? Promise.resolve()
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
    stores.current.set(threadId, pending)
    void pending.then(() => {
      if (stores.current.get(threadId) === pending) {
        stores.current.delete(threadId)
      }
    })
  }

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
      // Ticks made while the thread's entry was still on its way are the
      // user's for this thread: they stay, and the thread gets them.
      seenEdits.current = scopeEdits
      store(threadId, sourceScope)
    } else if (activeThread.source_scope !== undefined) {
      setSourceScope(activeThread.source_scope ?? EVERY_SOURCE)
    }
    // An entry without a scope was made by this client: the ticks on screen
    // opened it, and stay.
  })

  useEffect(() => {
    if (scopeEdits === seenEdits.current) return
    const current = shown.current
    if (current?.workspaceId !== workspaceId || current.threadId !== threadId) {
      return
    }
    seenEdits.current = scopeEdits
    if (threadId === null) writeDraftScope(workspaceId, sourceScope)
    else store(threadId, sourceScope)
  })
}
