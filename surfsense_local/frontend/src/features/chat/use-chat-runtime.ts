import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react"
import type { AppendMessage } from "@assistant-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  answerPermission,
  type PermissionReply,
  type PermissionRequest,
  type TurnSources,
} from "@/features/agent/api"
import { isOutdatedThreadRefusal } from "@/features/agent/outdated-thread"
import { isUnsupportedModelRefusal } from "@/features/agent/unsupported-model"
import { errorToast } from "@/features/feedback/error-toast"
import type { SourceScope } from "@/features/sources/tree/scope-state"
import { subscribeToWorkspaceChanges } from "@/features/workspaces/workspace-changes"
import { ApiError } from "@/lib/api"
import { intl } from "@/i18n/intl"

import {
  createThread,
  deleteThread,
  followRun,
  listMessages,
  listThreads,
  renameThread,
  stopRun,
  streamMessage,
  type ChatMessage,
  type ChatThread,
  type ImageUpload,
} from "./api"
import { ChatImageAdapter, previewOf, uploadsOf } from "./image-attachments"
import type { LiveThreadSource } from "./live-thread-runtime"
import { chatKeys } from "./query-keys"
import type { LivePair } from "./runs/apply-frame"
import {
  beginRun,
  dropRun,
  liveRun,
  onRunEnded,
  onRunFrame,
  pump,
  runSummaries,
  subscribeToRuns,
  updatePair,
  type RunState,
} from "./runs/run-store"
import { storedUploads } from "./runs/stored-uploads"
import { markRead, markUnread, readUnread } from "./runs/unread-replies"
import type { ChatErrorKind, ChatStreamEvent } from "./sse"
import { composedThread, isOptimistic, OPTIMISTIC_ID } from "./thread-messages"
import { readThinkingOn } from "./thinking-preference"

/** A backend error kind, or a refusal the app recognises before any stream:
 *  a turn on an agent thread that predates per-chat folders. */
export type ChatTurnErrorKind =
  ChatErrorKind | "agent_thread_outdated" | "agent_model_unsupported"

export type ChatTurnError = {
  // `interrupted`: the app closed under the reply; no frame carries it.
  kind: ChatTurnErrorKind | "interrupted"
  message: string
  provider: string
  /** The request failed before an SSE frame classified the backend error. */
  detailIsLocal?: boolean
  /** Only the thread's latest reply can be retried; older ones are a record. */
  retryable: boolean
}

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "chat_runtime_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function submittedText(message: AppendMessage) {
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim()
}

const EMPTY_THREADS: ChatThread[] = []
const EMPTY_MESSAGES: ChatMessage[] = []
const NO_APPROVALS: PermissionRequest[] = []

/** The thread's waiting requests without one that was answered. */
function withoutApproval(
  all: Record<number, PermissionRequest[]>,
  threadId: number,
  requestId: string
): Record<number, PermissionRequest[]> {
  const current = all[threadId]
  if (!current?.some((waiting) => waiting.id === requestId)) return all
  return {
    ...all,
    [threadId]: current.filter((waiting) => waiting.id !== requestId),
  }
}

/** Where the list says a thread's reply stands, as the run store spells it. */
function listedRunState(thread: ChatThread): RunState | null {
  if (!thread.running) return null
  const listed = thread.run_state
  if (listed?.state === "queued" && listed.position !== null) {
    return { state: "queued", position: listed.position }
  }
  if (listed?.state === "needs-approval") return { state: "needs-approval" }
  return { state: "running" }
}

function lastThreadKey(workspaceId: number) {
  return `surfsense:last-thread:${workspaceId}:v1`
}

const NEW_CHAT = "new"

export type ConversationView =
  | { status: "new" }
  | { status: "creating" }
  | { status: "active"; threadId: number }

function rememberThread(workspaceId: number, threadId: number | null) {
  try {
    localStorage.setItem(
      lastThreadKey(workspaceId),
      threadId === null ? NEW_CHAT : String(threadId)
    )
  } catch {
    // Selection remains valid for this session when storage is unavailable.
  }
}

function readStoredView(workspaceId: number): ConversationView {
  try {
    const stored = localStorage.getItem(lastThreadKey(workspaceId))
    if (stored === NEW_CHAT) return { status: "new" }
    const id = Number(stored)
    if (Number.isInteger(id) && id > 0) {
      return { status: "active", threadId: id }
    }
  } catch {
    // Private browsing: treat as a new chat.
  }
  return { status: "new" }
}

function stoppedBeforeAWord(pair: LivePair) {
  const reply = pair[1]
  return reply.content.ending?.type === "stopped" && !reply.content.text
}

/** Whether the stored turns already hold the run's whole reply. */
function storedTurnCaughtUp(canonical: ChatMessage[], pair: LivePair) {
  const ids = new Set(canonical.map((message) => message.id))
  return ids.has(pair[0].id) && ids.has(pair[1].id)
}

function optimisticPair(
  version: number,
  text: string,
  images: ImageUpload[],
  scope: TurnSources | null
): LivePair {
  return [
    {
      id: `${OPTIMISTIC_ID}user-${version}`,
      role: "user",
      content: {
        text,
        ...(images.length > 0 ? { previews: images.map(previewOf) } : {}),
        ...(scope ? { scope } : {}),
      },
      created_at: null,
      completed_at: null,
    },
    {
      id: `${OPTIMISTIC_ID}assistant-${version}`,
      role: "assistant",
      content: { text: "", citations: [] },
      created_at: null,
      completed_at: null,
    },
  ]
}

export function useChatRuntime({
  workspaceId,
  canSend,
  selectedDocumentIds,
  selectedSourceTitles,
  sourceScope = null,
  readsImages,
  canSkipThinking,
  onModelRequired,
}: {
  workspaceId: number
  canSend: boolean
  selectedDocumentIds: number[]
  // Each selected source's title, in the order of `selectedDocumentIds`.
  selectedSourceTitles: string[]
  // What the server resolves into the turn's sources, so none is left out.
  sourceScope?: SourceScope | null
  // Whether the selected model reads images; without it the composer has no
  // attachment adapter, so it takes none.
  readsImages: boolean
  // Whether the selected model can be told not to think; no other is asked to.
  canSkipThinking: boolean
  onModelRequired: () => void
}) {
  const queryClient = useQueryClient()
  const [conversationView, setConversationView] = useState<ConversationView>(
    () => readStoredView(workspaceId)
  )
  const [autoNamingThreadId, setAutoNamingThreadId] = useState<number | null>(
    null
  )
  // What was last set, so a streamed token can ask without queueing an
  // update of this page per token.
  const autoNamingRef = useRef<number | null>(null)
  const setAutoNaming = useCallback((threadId: number | null) => {
    autoNamingRef.current = threadId
    setAutoNamingThreadId(threadId)
  }, [])
  const [animatingTitleThreadId, setAnimatingTitleThreadId] = useState<
    number | null
  >(null)
  const [unreadThreadIds, setUnreadThreadIds] = useState<number[]>(() =>
    readUnread(workspaceId)
  )
  // The agent's requests waiting for the user, oldest first, per thread: a
  // turn keeps asking while its thread is not the one open.
  const [approvalsByThread, setApprovalsByThread] = useState<
    Record<number, PermissionRequest[]>
  >({})
  const requestVersion = useRef(0)

  // Where each run stands, never its text: a streamed token renders the open
  // thread's messages alone (LiveThreadRuntime), not this page.
  const runs = useSyncExternalStore(subscribeToRuns, runSummaries)

  const threadsQuery = useQuery({
    queryKey: chatKeys.threads(workspaceId),
    queryFn: ({ signal }) => listThreads(workspaceId, signal),
  })
  const threads = threadsQuery.data ?? EMPTY_THREADS
  const activeThreadId =
    conversationView.status === "active" ? conversationView.threadId : null
  const activeThreadIdRef = useRef(activeThreadId)
  activeThreadIdRef.current = activeThreadId
  const approvals =
    (activeThreadId !== null && approvalsByThread[activeThreadId]) ||
    NO_APPROVALS
  const activeThread = useMemo(
    () => threads.find((thread) => thread.id === activeThreadId) ?? null,
    [activeThreadId, threads]
  )

  const messagesQuery = useQuery({
    queryKey: chatKeys.messages(activeThreadId ?? -1),
    queryFn: ({ signal }) =>
      activeThreadId === null
        ? Promise.resolve(EMPTY_MESSAGES)
        : listMessages(activeThreadId, signal),
    enabled: activeThreadId !== null,
  })
  const persistedMessages = messagesQuery.data ?? EMPTY_MESSAGES
  const activeRun =
    activeThreadId === null ? null : (runs[activeThreadId] ?? null)
  const isRunning = activeRun !== null && !activeRun.ended

  const createThreadMutation = useMutation({
    mutationFn: ({ title, signal }: { title: string; signal: AbortSignal }) =>
      createThread(workspaceId, title, signal),
  })
  const deleteThreadMutation = useMutation({
    mutationFn: (threadId: number) => deleteThread(threadId),
  })
  const renameThreadMutation = useMutation({
    mutationFn: ({ threadId, title }: { threadId: number; title: string }) =>
      renameThread(threadId, title),
  })

  const selectThread = useCallback(
    (threadId: number) => {
      if (threadId === activeThreadId) {
        return
      }
      requestVersion.current += 1
      setConversationView({ status: "active", threadId })
      rememberThread(workspaceId, threadId)
      setUnreadThreadIds(markRead(workspaceId, threadId))
      setAutoNaming(null)
      setAnimatingTitleThreadId(null)
    },
    [activeThreadId, setAutoNaming, workspaceId]
  )

  const startNewChat = useCallback(() => {
    requestVersion.current += 1
    setConversationView({ status: "new" })
    rememberThread(workspaceId, null)
    setAutoNaming(null)
    setAnimatingTitleThreadId(null)
  }, [setAutoNaming, workspaceId])

  useEffect(() => {
    if (!threadsQuery.isSuccess) return
    if (conversationView.status !== "active") return
    if (threads.some((thread) => thread.id === conversationView.threadId)) {
      return
    }
    const fallback = threads[0]
    if (fallback) selectThread(fallback.id)
    else startNewChat()
  }, [
    conversationView,
    selectThread,
    startNewChat,
    threads,
    threadsQuery.isSuccess,
  ])

  // A run ended: the stored turns take over once they hold the reply, and a
  // thread that finished while another was open is marked unread.
  useEffect(
    () =>
      onRunEnded((threadId) => {
        // This window saw it end; the list need not be read again to know.
        queryClient.setQueryData<ChatThread[]>(
          chatKeys.threads(workspaceId),
          (current) =>
            current?.map((thread) =>
              thread.id === threadId
                ? { ...thread, running: false, run_state: null }
                : thread
            )
        )
        // A turn that ended asks nothing more.
        setApprovalsByThread((all) => {
          if (!all[threadId]) return all
          const rest = { ...all }
          delete rest[threadId]
          return rest
        })
        if (threadId !== activeThreadIdRef.current) {
          setUnreadThreadIds(markUnread(workspaceId, threadId))
        }
        void (async () => {
          const run = liveRun(threadId)
          const canonical = await queryClient
            .fetchQuery({
              queryKey: chatKeys.messages(threadId),
              queryFn: ({ signal }) => listMessages(threadId, signal),
              staleTime: 0,
            })
            .catch(() => null)
          if (!run?.pair) {
            dropRun(threadId)
          } else if (canonical && storedTurnCaughtUp(canonical, run.pair)) {
            dropRun(threadId)
          } else if (stoppedBeforeAWord(run.pair)) {
            // The API keeps nothing of a reply stopped before its first word.
            dropRun(threadId)
          } else if (!isOptimistic(run.pair[1].id)) {
            // Read before the store caught up: read again, and the live copy
            // goes once the stored turns hold it. A thread that is not open
            // has nothing reading it again, so it is read here, or its run
            // would stay until the thread is opened.
            const open = threadId === activeThreadIdRef.current
            await queryClient
              .invalidateQueries({
                queryKey: chatKeys.messages(threadId),
                refetchType: open ? "active" : "all",
              })
              .catch(() => undefined)
            const stored = queryClient.getQueryData<ChatMessage[]>(
              chatKeys.messages(threadId)
            )
            const held = liveRun(threadId)
            if (
              !open &&
              stored &&
              held?.ended &&
              held.pair?.[1].id === run.pair[1].id &&
              storedTurnCaughtUp(stored, held.pair)
            ) {
              dropRun(threadId)
            }
          }
          // An optimistic pair is a request that never reached the API; its
          // error stays on screen until the person moves on.
        })()
      }),
    [queryClient, workspaceId]
  )

  useEffect(() => {
    if (activeThreadId === null || !activeRun?.ended) return
    const run = liveRun(activeThreadId)
    if (run?.pair && storedTurnCaughtUp(persistedMessages, run.pair)) {
      dropRun(activeThreadId)
    }
  }, [activeRun, activeThreadId, persistedMessages])

  // Frames the reply itself does not hold: a new title, and the agent's asks.
  useEffect(
    () =>
      onRunFrame((threadId, event: ChatStreamEvent) => {
        if (event.type === "thread-title-update") {
          setAutoNaming(null)
          setAnimatingTitleThreadId(threadId)
          queryClient.setQueryData<ChatThread[]>(
            chatKeys.threads(workspaceId),
            (current = []) =>
              current.map((thread) =>
                thread.id === threadId
                  ? { ...thread, title: event.title }
                  : thread
              )
          )
        } else if (event.type === "delta") {
          if (autoNamingRef.current === threadId) setAutoNaming(null)
        } else if (event.type === "permission-request") {
          const { id, permission, patterns, command } = event
          setApprovalsByThread((all) => {
            const current = all[threadId] ?? []
            return current.some((waiting) => waiting.id === id)
              ? all
              : {
                  ...all,
                  [threadId]: [
                    ...current,
                    { id, permission, patterns, command },
                  ],
                }
          })
        } else if (event.type === "permission-replied") {
          setApprovalsByThread((all) =>
            withoutApproval(all, threadId, event.id)
          )
        }
      }),
    [queryClient, setAutoNaming, workspaceId]
  )

  // Another window, or this one after a reload, may have started a run: the
  // list says so, and the thread's reply is followed from its first frame.
  useEffect(
    () =>
      subscribeToWorkspaceChanges(workspaceId, "chat-runs", (change) => {
        void queryClient.invalidateQueries({
          queryKey: chatKeys.threads(workspaceId),
        })
        if (change?.status !== "done") return
        for (const threadId of change.ids) {
          if (liveRun(threadId)) continue
          if (threadId === activeThreadIdRef.current) {
            void queryClient.invalidateQueries({
              queryKey: chatKeys.messages(threadId),
            })
          } else {
            setUnreadThreadIds(markUnread(workspaceId, threadId))
          }
        }
      }),
    [queryClient, workspaceId]
  )

  useEffect(() => {
    if (activeThread === null || !activeThread.running) return
    if (liveRun(activeThread.id)) return
    const threadId = activeThread.id
    const signal = beginRun(threadId)
    void pump(threadId, followRun(threadId, 0, signal)).catch(() => undefined)
  }, [activeThread])

  const removeThread = async (threadId: number) => {
    try {
      await deleteThreadMutation.mutateAsync(threadId)
      dropRun(threadId)
      const next = threads.filter((thread) => thread.id !== threadId)
      queryClient.setQueryData(chatKeys.threads(workspaceId), next)
      queryClient.removeQueries({ queryKey: chatKeys.messages(threadId) })
      setUnreadThreadIds(markRead(workspaceId, threadId))
      if (activeThreadId === threadId) {
        if (next[0]) {
          selectThread(next[0].id)
        } else {
          startNewChat()
        }
      }
    } catch (cause) {
      errorToast(
        intl.formatMessage({
          id: "chat_runtime_delete_toast",
          defaultMessage: "Couldn’t delete chat",
        }),
        {
          description: messageFrom(cause),
        }
      )
    }
  }

  const rename = async (threadId: number, title: string) => {
    try {
      const renamed = await renameThreadMutation.mutateAsync({
        threadId,
        title,
      })
      setAnimatingTitleThreadId(null)
      queryClient.setQueryData<ChatThread[]>(
        chatKeys.threads(workspaceId),
        (current = []) =>
          current.map((thread) => (thread.id === renamed.id ? renamed : thread))
      )
      return true
    } catch (cause) {
      errorToast(
        intl.formatMessage({
          id: "chat_runtime_rename_toast",
          defaultMessage: "Couldn’t rename chat",
        }),
        {
          description: messageFrom(cause),
        }
      )
      return false
    }
  }

  const send = useCallback(
    async (
      typed: string,
      images: ImageUpload[] = [],
      retryOf: number | null = null,
      replaces: ReadonlyArray<number | string> = []
    ) => {
      // The backend needs a question for retrieval and the title; an image sent
      // alone asks the obvious one.
      const text =
        typed ||
        (images.length > 0
          ? intl.formatMessage({
              id: "chat_runtime_image_question_body",
              defaultMessage: "What is in this image?",
            })
          : "")
      if (
        !text ||
        isRunning ||
        !canSend ||
        conversationView.status === "creating"
      ) {
        return
      }

      const version = ++requestVersion.current
      let threadId =
        conversationView.status === "active" ? conversationView.threadId : null
      let usesAgent =
        threads.find((thread) => thread.id === threadId)?.uses_agent ?? false
      try {
        if (threadId === null) {
          setConversationView({ status: "creating" })
          const thread = await createThreadMutation.mutateAsync({
            title: "New chat",
            signal: new AbortController().signal,
          })
          if (requestVersion.current !== version) {
            return
          }
          threadId = thread.id
          usesAgent = thread.uses_agent
          queryClient.setQueryData<ChatThread[]>(
            chatKeys.threads(workspaceId),
            (current = []) => [
              thread,
              ...current.filter((candidate) => candidate.id !== thread.id),
            ]
          )
          queryClient.setQueryData(chatKeys.messages(thread.id), EMPTY_MESSAGES)
          setConversationView({ status: "active", threadId: thread.id })
          setAutoNaming(thread.id)
          rememberThread(workspaceId, thread.id)
        }
      } catch (cause) {
        if (requestVersion.current === version) {
          setConversationView({ status: "new" })
        }
        errorToast(messageFrom(cause))
        return
      }

      const runThreadId = threadId
      const signal = beginRun(runThreadId, {
        pair: optimisticPair(
          version,
          text,
          images,
          // The agent works from these alone; a chat's turn shows no line.
          usesAgent
            ? {
                document_ids: selectedDocumentIds,
                titles: selectedSourceTitles,
              }
            : null
        ),
        replaces,
        retry: { text, images },
      })
      try {
        await pump(
          runThreadId,
          streamMessage(
            runThreadId,
            text,
            images,
            selectedDocumentIds,
            sourceScope,
            !canSkipThinking || readThinkingOn(),
            retryOf,
            signal
          )
        )
      } catch (cause) {
        if (
          cause instanceof ApiError &&
          cause.status === 409 &&
          cause.message.includes("no chat model selected")
        ) {
          dropRun(runThreadId)
          onModelRequired()
        } else if (isOutdatedThreadRefusal(cause)) {
          updatePair(runThreadId, ([user, assistant]) => [
            user,
            {
              ...assistant,
              content: {
                ...assistant.content,
                ending: {
                  type: "error",
                  kind: "agent_thread_outdated",
                  message: "",
                },
              },
            },
          ])
        } else if (isUnsupportedModelRefusal(cause)) {
          updatePair(runThreadId, ([user, assistant]) => [
            user,
            {
              ...assistant,
              content: {
                ...assistant.content,
                ending: {
                  type: "error",
                  kind: "agent_model_unsupported",
                  message: "",
                },
              },
            },
          ])
        } else if (!isAbort(cause)) {
          // The request to our own backend failed before any SSE frame could
          // classify it (network drop, bad response, etc.) — "unknown" maps
          // to a plain Retry, with no Model setup CTA that wouldn't apply.
          updatePair(runThreadId, ([user, assistant]) => [
            user,
            {
              ...assistant,
              content: {
                ...assistant.content,
                ending: {
                  type: "error",
                  kind: "unknown",
                  message: cause instanceof Error ? cause.message : "",
                  local: true,
                },
              },
            },
          ])
        }
      } finally {
        if (autoNamingRef.current === runThreadId) setAutoNaming(null)
      }
    },
    [
      canSend,
      canSkipThinking,
      conversationView,
      createThreadMutation,
      isRunning,
      onModelRequired,
      queryClient,
      selectedDocumentIds,
      selectedSourceTitles,
      setAutoNaming,
      sourceScope,
      threads,
      workspaceId,
    ]
  )

  const onNew = useCallback(
    (appendMessage: AppendMessage) =>
      send(submittedText(appendMessage), uploadsOf(appendMessage)),
    [send]
  )

  const retry = useCallback(
    (assistantId: string) => {
      if (activeThreadId === null) return
      const threadId = activeThreadId
      const held = liveRun(threadId)
      // Read when asked, not held from a render: a streamed token would
      // otherwise make a new Retry for every message in the thread.
      const shown = composedThread(
        queryClient.getQueryData<ChatMessage[]>(chatKeys.messages(threadId)) ??
          EMPTY_MESSAGES,
        held?.pair ?? null,
        held?.replaces ?? []
      )
      const index = shown.findIndex(
        (message) => String(message.id) === assistantId
      )
      const failed = shown[index]
      const question = shown[index - 1]
      const latest = shown.findLast((message) => message.role === "assistant")
      if (!failed || question?.role !== "user" || latest !== failed) {
        return
      }
      void (async () => {
        const images =
          held?.retry && held.pair && String(held.pair[1].id) === assistantId
            ? held.retry.images
            : await storedUploads(threadId, question).catch(() => [])
        // A stored failure is replaced in place; an agent's turns, and a
        // request that never reached the API, are simply sent again.
        const retryOf =
          activeThread?.uses_agent || typeof failed.id !== "number"
            ? null
            : failed.id
        await send(question.content.text ?? "", images, retryOf, [
          question.id,
          failed.id,
        ])
      })()
    },
    [activeThread, activeThreadId, queryClient, send]
  )

  const cancel = useCallback(async () => {
    const threadId = activeThreadIdRef.current
    if (threadId === null) return
    updatePair(threadId, ([user, assistant]) => [
      user,
      {
        ...assistant,
        content: { ...assistant.content, ending: { type: "stopped" } },
      },
    ])
    try {
      await stopRun(threadId)
    } catch (cause) {
      errorToast(messageFrom(cause))
    }
  }, [])

  const answerApproval = useCallback(
    async (request: PermissionRequest, reply: PermissionReply) => {
      if (activeThreadId === null) return
      try {
        await answerPermission(activeThreadId, request.id, reply)
        setApprovalsByThread((all) =>
          withoutApproval(all, activeThreadId, request.id)
        )
      } catch (cause) {
        errorToast(
          intl.formatMessage({
            id: "chat_runtime_approval_toast",
            defaultMessage: "Couldn’t send your answer to the agent",
          }),
          { description: messageFrom(cause) }
        )
      }
    },
    [activeThreadId]
  )

  const finishTitleAnimation = useCallback(() => {
    setAnimatingTitleThreadId(null)
  }, [])

  const isLoadingThreads = threadsQuery.isPending
  const isLoadingMessages =
    activeThreadId !== null && !activeRun?.hasPair && messagesQuery.isPending

  useEffect(() => {
    if (threadsQuery.error) {
      errorToast(
        intl.formatMessage({
          id: "chat_runtime_load_threads_toast",
          defaultMessage: "Couldn’t load your chats",
        }),
        {
          description: messageFrom(threadsQuery.error),
        }
      )
    }
  }, [threadsQuery.error])

  useEffect(() => {
    if (messagesQuery.error) {
      errorToast(
        intl.formatMessage({
          id: "chat_runtime_load_messages_toast",
          defaultMessage: "Couldn’t load this chat",
        }),
        {
          description: messageFrom(messagesQuery.error),
        }
      )
    }
  }, [messagesQuery.error])

  const adapters = useMemo(
    () => (readsImages ? { attachments: new ChatImageAdapter() } : undefined),
    [readsImages]
  )

  const isSendDisabled = !canSend || isLoadingMessages || isLoadingThreads
  // For LiveThreadRuntime, which turns it and the run into the open thread.
  const liveThread = useMemo<LiveThreadSource>(
    () => ({
      threadId: activeThreadId,
      persistedMessages,
      adapters,
      isSendDisabled,
      onNew,
      onCancel: cancel,
    }),
    [activeThreadId, adapters, cancel, isSendDisabled, onNew, persistedMessages]
  )

  // Where each thread's reply stands: what the list says, sharpened by what
  // this window follows itself, which hears each change first.
  const runStates = useMemo(() => {
    const states: Record<number, RunState> = {}
    for (const thread of threads) {
      const listed = listedRunState(thread)
      if (listed) states[thread.id] = listed
    }
    for (const [threadId, run] of Object.entries(runs)) {
      if (!run.ended) states[Number(threadId)] = run.state
    }
    return states
  }, [threads, runs])

  return {
    liveThread,
    threads,
    conversationView,
    activeThread,
    activeThreadId,
    isLoadingThreads,
    isLoadingMessages,
    isRunning,
    runStates,
    unreadThreadIds,
    autoNamingThreadId,
    animatingTitleThreadId,
    finishTitleAnimation,
    selectThread,
    startNewChat,
    rename,
    removeThread,
    retry,
    approvals,
    answerApproval,
  }
}
