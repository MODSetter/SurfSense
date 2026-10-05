import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react"
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  answerPermission,
  type PermissionReply,
  type PermissionRequest,
} from "@/features/agent/api"
import { errorToast } from "@/features/feedback/error-toast"
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
import {
  ChatImageAdapter,
  attachmentsOf,
  previewOf,
  uploadsOf,
} from "./image-attachments"
import { chatKeys } from "./query-keys"
import type { LivePair } from "./runs/apply-frame"
import {
  abandonRun,
  beginRun,
  dropRun,
  liveRun,
  liveRuns,
  onRunEnded,
  onRunFrame,
  pump,
  runsVersion,
  subscribeToRuns,
  updatePair,
  type LiveRun,
  type RunState,
} from "./runs/run-store"
import { storedUploads } from "./runs/stored-uploads"
import { markRead, markUnread, readUnread } from "./runs/unread-replies"
import type { ChatErrorKind, ChatStreamEvent } from "./sse"
import { readThinkingOn } from "./thinking-preference"

export type ChatTurnError = {
  // `interrupted`: the app closed under the reply; no frame carries it.
  kind: ChatErrorKind | "interrupted"
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

const OPTIMISTIC_ID = "optimistic-"

function isOptimistic(id: number | string) {
  return String(id).startsWith(OPTIMISTIC_ID)
}

/**
 * The thread as shown: its stored turns, with the reply a run is writing in
 * place of its stored copy. The question is the stored one once it exists,
 * which a reattached run never had the text of.
 */
function composed(
  persisted: ChatMessage[],
  run: LiveRun | null
): ChatMessage[] {
  if (!run?.pair) return persisted
  const [user, assistant] = run.pair
  const hidden = new Set([...run.replaces, user.id, assistant.id])
  const question = persisted.find((message) => message.id === user.id) ?? user
  return [
    ...persisted.filter((message) => !hidden.has(message.id)),
    question,
    assistant,
  ]
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

function errorOf(
  message: ChatMessage,
  latestAssistantId: string | null
): ChatTurnError | null {
  const ending = message.content.ending
  const retryable = String(message.id) === latestAssistantId
  if (ending?.type === "error") {
    return {
      kind: ending.kind,
      message: ending.message,
      provider: ending.provider ?? "",
      detailIsLocal: ending.local,
      retryable,
    }
  }
  if (ending?.type === "interrupted") {
    return { kind: "interrupted", message: "", provider: "", retryable }
  }
  return null
}

function toRuntimeMessage(
  message: ChatMessage,
  latestAssistantId: string | null,
  threadId: number | null
): ThreadMessageLike {
  const value =
    message.role === "assistant" ? message.completed_at : message.created_at
  // SQLite stores CURRENT_TIMESTAMP in UTC but returns it without an offset.
  const timestamp =
    value && !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? `${value}Z` : value
  const error =
    message.role === "assistant" ? errorOf(message, latestAssistantId) : null
  const stopped =
    message.role === "assistant" && message.content.ending?.type === "stopped"
  return {
    id: String(message.id),
    role: message.role,
    content: [{ type: "text", text: message.content.text ?? "" }],
    ...(message.role === "user"
      ? { attachments: attachmentsOf(message, threadId) }
      : {}),
    ...(timestamp ? { createdAt: new Date(timestamp) } : {}),
    ...(error
      ? { status: { type: "incomplete", reason: "error", error } as const }
      : stopped
        ? // Without it assistant-ui calls a stopped reply complete.
          { status: { type: "incomplete", reason: "cancelled" } as const }
        : {}),
    metadata: {
      custom: {
        citations: message.content.citations ?? [],
        steps: message.content.steps ?? [],
        reasoning: message.content.reasoning
          ? {
              text: message.content.reasoning.text,
              durationMs: message.content.reasoning.duration_ms,
            }
          : null,
        progress: message.content.progress ?? null,
        queue: message.content.queue ?? null,
      },
    },
  }
}

function optimisticPair(
  version: number,
  text: string,
  images: ImageUpload[]
): LivePair {
  return [
    {
      id: `${OPTIMISTIC_ID}user-${version}`,
      role: "user",
      content: {
        text,
        ...(images.length > 0 ? { previews: images.map(previewOf) } : {}),
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
  readsImages,
  canSkipThinking,
  onModelRequired,
}: {
  workspaceId: number
  canSend: boolean
  selectedDocumentIds: number[]
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
  const [animatingTitleThreadId, setAnimatingTitleThreadId] = useState<
    number | null
  >(null)
  const [unreadThreadIds, setUnreadThreadIds] = useState<number[]>(() =>
    readUnread(workspaceId)
  )
  // The agent's requests waiting for the user, oldest first.
  const [approvals, setApprovals] = useState<PermissionRequest[]>([])
  const requestVersion = useRef(0)

  // Re-render on every change to any run, wherever its thread is.
  useSyncExternalStore(subscribeToRuns, runsVersion)

  const threadsQuery = useQuery({
    queryKey: chatKeys.threads(workspaceId),
    queryFn: ({ signal }) => listThreads(workspaceId, signal),
  })
  const threads = threadsQuery.data ?? EMPTY_THREADS
  const activeThreadId =
    conversationView.status === "active" ? conversationView.threadId : null
  const activeThreadIdRef = useRef(activeThreadId)
  activeThreadIdRef.current = activeThreadId
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
  const activeRun = liveRun(activeThreadId)
  const isRunning = activeRun !== null && !activeRun.ended
  const threadMessages = composed(persistedMessages, activeRun)

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

  const leaveAgentTurn = useCallback(() => {
    // An agent turn is not a background run: leaving its thread ends it.
    const leaving = activeThreadIdRef.current
    if (leaving === null) return
    const thread = threads.find((candidate) => candidate.id === leaving)
    if (thread?.uses_agent) abandonRun(leaving)
  }, [threads])

  const selectThread = useCallback(
    (threadId: number) => {
      if (threadId === activeThreadId) {
        return
      }
      leaveAgentTurn()
      requestVersion.current += 1
      setConversationView({ status: "active", threadId })
      rememberThread(workspaceId, threadId)
      setUnreadThreadIds(markRead(workspaceId, threadId))
      setApprovals([])
      setAutoNamingThreadId(null)
      setAnimatingTitleThreadId(null)
    },
    [activeThreadId, leaveAgentTurn, workspaceId]
  )

  const startNewChat = useCallback(() => {
    leaveAgentTurn()
    requestVersion.current += 1
    setConversationView({ status: "new" })
    rememberThread(workspaceId, null)
    setApprovals([])
    setAutoNamingThreadId(null)
    setAnimatingTitleThreadId(null)
  }, [leaveAgentTurn, workspaceId])

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
              thread.id === threadId ? { ...thread, running: false } : thread
            )
        )
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
            // goes once the stored turns hold it.
            void queryClient.invalidateQueries({
              queryKey: chatKeys.messages(threadId),
            })
          }
          // An optimistic pair is a request that never reached the API; its
          // error stays on screen until the person moves on.
        })()
      }),
    [queryClient, workspaceId]
  )

  useEffect(() => {
    if (activeRun?.ended && activeRun.pair) {
      if (storedTurnCaughtUp(persistedMessages, activeRun.pair)) {
        dropRun(activeRun.threadId)
      }
    }
  }, [activeRun, persistedMessages])

  // Frames the reply itself does not hold: a new title, and the agent's asks.
  useEffect(
    () =>
      onRunFrame((threadId, event: ChatStreamEvent) => {
        if (event.type === "thread-title-update") {
          setAutoNamingThreadId(null)
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
          setAutoNamingThreadId((current) =>
            current === threadId ? null : current
          )
        } else if (
          event.type === "permission-request" &&
          threadId === activeThreadIdRef.current
        ) {
          const { id, permission, patterns, command } = event
          setApprovals((current) =>
            current.some((waiting) => waiting.id === id)
              ? current
              : [...current, { id, permission, patterns, command }]
          )
        } else if (event.type === "permission-replied") {
          setApprovals((current) =>
            current.filter((waiting) => waiting.id !== event.id)
          )
        }
      }),
    [queryClient, workspaceId]
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
    if (activeThread.uses_agent || liveRun(activeThread.id)) return
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
          queryClient.setQueryData<ChatThread[]>(
            chatKeys.threads(workspaceId),
            (current = []) => [
              thread,
              ...current.filter((candidate) => candidate.id !== thread.id),
            ]
          )
          queryClient.setQueryData(chatKeys.messages(thread.id), EMPTY_MESSAGES)
          setConversationView({ status: "active", threadId: thread.id })
          setAutoNamingThreadId(thread.id)
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
        pair: optimisticPair(version, text, images),
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
        setAutoNamingThreadId((current) =>
          current === runThreadId ? null : current
        )
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
      const index = threadMessages.findIndex(
        (message) => String(message.id) === assistantId
      )
      const failed = threadMessages[index]
      const question = threadMessages[index - 1]
      const latest = threadMessages.findLast(
        (message) => message.role === "assistant"
      )
      if (
        !failed ||
        question?.role !== "user" ||
        latest !== failed ||
        activeThreadId === null
      ) {
        return
      }
      const threadId = activeThreadId
      const held = liveRun(threadId)
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
    [activeThread, activeThreadId, send, threadMessages]
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
    if (activeThread?.uses_agent) {
      abandonRun(threadId)
      return
    }
    try {
      await stopRun(threadId)
    } catch (cause) {
      errorToast(messageFrom(cause))
    }
  }, [activeThread])

  const answerApproval = useCallback(
    async (request: PermissionRequest, reply: PermissionReply) => {
      if (activeThreadId === null) return
      try {
        await answerPermission(activeThreadId, request.id, reply)
        setApprovals((current) =>
          current.filter((waiting) => waiting.id !== request.id)
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
    activeThreadId !== null && !activeRun?.pair && messagesQuery.isPending

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

  const latestAssistantId = useMemo(() => {
    const latest = threadMessages.findLast(
      (message) => message.role === "assistant"
    )
    return latest ? String(latest.id) : null
  }, [threadMessages])

  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages: threadMessages,
    convertMessage: (message) =>
      toRuntimeMessage(message, latestAssistantId, activeThreadId),
    adapters,
    onNew,
    isRunning,
    isSendDisabled: !canSend || isLoadingMessages || isLoadingThreads,
    onCancel: cancel,
  })

  // Where each thread's reply stands: what the list says, sharpened by what
  // this window follows itself, which alone knows a place in line.
  const runStates = useMemo(() => {
    const states: Record<number, RunState> = {}
    for (const thread of threads) {
      if (thread.running) states[thread.id] = { state: "running" }
    }
    for (const run of liveRuns()) {
      if (!run.ended) states[run.threadId] = run.state
    }
    return states
    // `runsVersion` is what changes when a run does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threads, runsVersion()])

  return {
    runtime,
    threads,
    conversationView,
    activeThread,
    activeThreadId,
    messages: threadMessages,
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
