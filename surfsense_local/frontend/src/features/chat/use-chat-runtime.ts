import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  answerPermission,
  type AgentStep,
  type PermissionReply,
  type PermissionRequest,
} from "@/features/agent/api"
import { isOutdatedThreadRefusal } from "@/features/agent/outdated-thread"
import { errorToast } from "@/features/feedback/error-toast"
import type { SourceScope } from "@/features/sources/tree/scope-state"
import { ApiError } from "@/lib/api"
import { intl } from "@/i18n/intl"

import {
  createThread,
  deleteThread,
  listMessages,
  listThreads,
  renameThread,
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
import type { ChatErrorKind, ChatStreamEvent } from "./sse"
import { readThinkingOn } from "./thinking-preference"

/** A backend error kind, or a refusal the app recognises before any stream:
 *  a turn on an agent thread that predates per-chat folders. */
export type ChatTurnErrorKind = ChatErrorKind | "agent_thread_outdated"

export type ChatTurnError = {
  kind: ChatTurnErrorKind
  message: string
  provider: string
  retryText: string
  retryImages: ImageUpload[]
  /** The request failed before an SSE frame classified the backend error. */
  detailIsLocal?: boolean
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

function hasCanonicalTurn(
  threadMessages: ChatMessage[],
  userMessageId: number | string,
  assistantMessageId: number | string
) {
  const ids = new Set(threadMessages.map((message) => message.id))
  return ids.has(userMessageId) && ids.has(assistantMessageId)
}

const OPTIMISTIC_ID = "optimistic-"

function areLiveMessagesPersisted(
  liveMessages: ChatMessage[],
  persistedMessages: ChatMessage[]
) {
  const persistedIds = new Set(persistedMessages.map((message) => message.id))
  // A stored id is the database's number or, in an agent thread, opencode's
  // string; only the placeholders sent before `accepted` are neither.
  return liveMessages.every(
    (message) =>
      !String(message.id).startsWith(OPTIMISTIC_ID) &&
      persistedIds.has(message.id)
  )
}

/** The step an `agent-step` frame describes, without the frame's own type. */
function stepFrom(
  event: Extract<ChatStreamEvent, { type: "agent-step" }>
): AgentStep {
  const { id, tool, status, title, input, output, error, artifact } = event
  return { id, tool, status, title, input, output, error, artifact }
}

/** The request a `permission-request` frame describes. */
function requestFrom(
  event: Extract<ChatStreamEvent, { type: "permission-request" }>
): PermissionRequest {
  const { id, permission, patterns, command } = event
  return { id, permission, patterns, command }
}

/** The reply's steps with this one added, or updated where it already is. */
function withStep(steps: AgentStep[] | undefined, step: AgentStep) {
  const current = steps ?? []
  return current.some((candidate) => candidate.id === step.id)
    ? current.map((candidate) => (candidate.id === step.id ? step : candidate))
    : [...current, step]
}

function toRuntimeMessage(
  message: ChatMessage,
  chatErrors: Record<string, ChatTurnError>,
  threadId: number | null
): ThreadMessageLike {
  const value =
    message.role === "assistant" ? message.completed_at : message.created_at
  // SQLite stores CURRENT_TIMESTAMP in UTC but returns it without an offset.
  const timestamp =
    value && !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? `${value}Z` : value
  const error =
    message.role === "assistant" ? chatErrors[String(message.id)] : undefined
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
        preparing: message.content.preparing ?? null,
        scope: message.content.scope ?? null,
      },
    },
  }
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
  const [liveMessages, setLiveMessages] = useState<ChatMessage[] | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [autoNamingThreadId, setAutoNamingThreadId] = useState<number | null>(
    null
  )
  const [animatingTitleThreadId, setAnimatingTitleThreadId] = useState<
    number | null
  >(null)
  const [chatErrors, setChatErrors] = useState<Record<string, ChatTurnError>>(
    {}
  )
  // The agent's requests waiting for the user, oldest first.
  const [approvals, setApprovals] = useState<PermissionRequest[]>([])
  const streamController = useRef<AbortController | null>(null)
  const requestVersion = useRef(0)

  const threadsQuery = useQuery({
    queryKey: chatKeys.threads(workspaceId),
    queryFn: ({ signal }) => listThreads(workspaceId, signal),
  })
  const threads = threadsQuery.data ?? EMPTY_THREADS
  const activeThreadId =
    conversationView.status === "active" ? conversationView.threadId : null

  const messagesQuery = useQuery({
    queryKey: [...chatKeys.all, "messages", activeThreadId] as const,
    queryFn: ({ signal }) =>
      activeThreadId === null
        ? Promise.resolve(EMPTY_MESSAGES)
        : listMessages(activeThreadId, signal),
    enabled: activeThreadId !== null,
  })
  const persistedMessages = messagesQuery.data ?? EMPTY_MESSAGES
  const usesLiveMessages =
    liveMessages !== null &&
    (isRunning || !areLiveMessagesPersisted(liveMessages, persistedMessages))
  const threadMessages = usesLiveMessages ? liveMessages : persistedMessages

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
      streamController.current?.abort()
      requestVersion.current += 1
      setConversationView({ status: "active", threadId })
      rememberThread(workspaceId, threadId)
      setLiveMessages(null)
      setChatErrors({})
      setApprovals([])
      setIsRunning(false)
      setAutoNamingThreadId(null)
      setAnimatingTitleThreadId(null)
    },
    [activeThreadId, workspaceId]
  )

  useEffect(() => {
    return () => {
      streamController.current?.abort()
      requestVersion.current += 1
    }
  }, [])

  const startNewChat = useCallback(() => {
    streamController.current?.abort()
    requestVersion.current += 1
    setConversationView({ status: "new" })
    rememberThread(workspaceId, null)
    setLiveMessages(null)
    setChatErrors({})
    setApprovals([])
    setIsRunning(false)
    setAutoNamingThreadId(null)
    setAnimatingTitleThreadId(null)
  }, [workspaceId])

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

  const removeThread = async (threadId: number) => {
    try {
      await deleteThreadMutation.mutateAsync(threadId)
      const next = threads.filter((thread) => thread.id !== threadId)
      queryClient.setQueryData(chatKeys.threads(workspaceId), next)
      queryClient.removeQueries({ queryKey: chatKeys.messages(threadId) })
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
    async (typed: string, images: ImageUpload[] = []) => {
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

      const controller = new AbortController()
      streamController.current?.abort()
      streamController.current = controller
      const version = ++requestVersion.current
      setIsRunning(true)

      let threadId =
        conversationView.status === "active" ? conversationView.threadId : null
      let usesAgent =
        threads.find((thread) => thread.id === threadId)?.uses_agent ?? false
      let userMessageId: number | string | null = null
      let assistantMessageId: number | string | null = null
      // Declared here (not inside the try) so the catch block below can still
      // attach a failure to the right message, whether or not "accepted" ever
      // remapped these to real ids.
      let userId: number | string = `optimistic-user-${version}`
      let assistantId: number | string = `optimistic-assistant-${version}`
      let preparing = false
      try {
        if (threadId === null) {
          setConversationView({ status: "creating" })
          const thread = await createThreadMutation.mutateAsync({
            title: "New chat",
            signal: controller.signal,
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
          setAutoNamingThreadId(thread.id)
          rememberThread(workspaceId, thread.id)
        }

        const currentMessages =
          queryClient.getQueryData<ChatMessage[]>(
            chatKeys.messages(threadId)
          ) ?? EMPTY_MESSAGES
        setLiveMessages([
          ...currentMessages,
          {
            id: userId,
            role: "user",
            content: {
              text,
              ...(images.length > 0 ? { previews: images.map(previewOf) } : {}),
              // The agent works from these alone; a chat's turn shows no line.
              ...(usesAgent
                ? {
                    scope: {
                      document_ids: selectedDocumentIds,
                      titles: selectedSourceTitles,
                    },
                  }
                : {}),
            },
            created_at: null,
            completed_at: null,
          },
          {
            id: assistantId,
            role: "assistant",
            content: { text: "", citations: [] },
            created_at: null,
            completed_at: null,
          },
        ])

        await streamMessage(
          threadId,
          text,
          images,
          selectedDocumentIds,
          sourceScope,
          !canSkipThinking || readThinkingOn(),
          controller.signal,
          (event) => {
            if (requestVersion.current !== version) {
              return
            }
            // Shown from the first frame until any other arrives.
            if (preparing && event.type !== "agent-preparing") {
              preparing = false
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: { ...message.content, preparing: undefined },
                        }
                      : message
                  ) ?? null
              )
            }
            if (event.type === "agent-preparing") {
              preparing = true
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            preparing: event.count,
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "accepted") {
              const previousUserId = userId
              const previousAssistantId = assistantId
              const nextUserId = event.user_message_id
              const nextAssistantId = event.assistant_message_id
              userMessageId = nextUserId
              assistantMessageId = nextAssistantId
              userId = nextUserId
              assistantId = nextAssistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) => {
                    if (message.id === previousUserId) {
                      return {
                        ...message,
                        id: nextUserId,
                        created_at: event.user_created_at,
                      }
                    }
                    if (message.id === previousAssistantId) {
                      return { ...message, id: nextAssistantId }
                    }
                    return message
                  }) ?? null
              )
            } else if (event.type === "completed") {
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          completed_at: event.assistant_completed_at,
                          content: {
                            ...message.content,
                            ...(event.text !== undefined
                              ? { text: event.text }
                              : {}),
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "agent-scope") {
              // The server's resolution replaces the panel's guess.
              const targetId = userId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: { ...message.content, scope: event.scope },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "thread-title-update") {
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
            } else if (
              event.type === "citation-catalog" ||
              event.type === "citations"
            ) {
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            citations: event.items,
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "prompt-progress") {
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            progress: {
                              processed: event.processed,
                              total: event.total,
                            },
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "reasoning") {
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            reasoning: {
                              text:
                                (message.content.reasoning?.text ?? "") +
                                event.text,
                              duration_ms: null,
                            },
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "reasoning-end") {
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId && message.content.reasoning
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            reasoning: {
                              ...message.content.reasoning,
                              duration_ms: event.duration_ms,
                            },
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "delta") {
              setAutoNamingThreadId(null)
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            text: (message.content.text ?? "") + event.text,
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "agent-step") {
              const step = stepFrom(event)
              const targetId = assistantId
              setLiveMessages(
                (current) =>
                  current?.map((message) =>
                    message.id === targetId
                      ? {
                          ...message,
                          content: {
                            ...message.content,
                            steps: withStep(message.content.steps, step),
                          },
                        }
                      : message
                  ) ?? null
              )
            } else if (event.type === "permission-request") {
              const request = requestFrom(event)
              setApprovals((current) =>
                current.some((waiting) => waiting.id === request.id)
                  ? current
                  : [...current, request]
              )
            } else if (event.type === "permission-replied") {
              setApprovals((current) =>
                current.filter((waiting) => waiting.id !== event.id)
              )
            } else if (event.type === "error") {
              const failedId = assistantId
              setChatErrors((current) => ({
                ...current,
                [String(failedId)]: {
                  kind: event.kind,
                  message: event.message,
                  provider: event.provider,
                  retryText: text,
                  retryImages: images,
                },
              }))
            }
          }
        )

        if (
          requestVersion.current === version &&
          userMessageId !== null &&
          assistantMessageId !== null
        ) {
          const completedThreadId = threadId
          const canonical = await queryClient.fetchQuery({
            queryKey: chatKeys.messages(completedThreadId),
            queryFn: ({ signal }) => listMessages(completedThreadId, signal),
            staleTime: 0,
          })
          if (
            requestVersion.current === version &&
            hasCanonicalTurn(canonical, userMessageId, assistantMessageId)
          ) {
            setLiveMessages(null)
          } else {
            void queryClient.invalidateQueries({
              queryKey: chatKeys.messages(completedThreadId),
            })
          }
        }
      } catch (cause) {
        if (threadId === null && requestVersion.current === version) {
          setConversationView({ status: "new" })
        }
        if (
          cause instanceof ApiError &&
          cause.status === 409 &&
          cause.message.includes("no chat model selected")
        ) {
          onModelRequired()
        } else if (
          isOutdatedThreadRefusal(cause) &&
          requestVersion.current === version
        ) {
          setChatErrors((current) => ({
            ...current,
            [String(assistantId)]: {
              kind: "agent_thread_outdated",
              message: "",
              provider: "",
              retryText: text,
              retryImages: images,
            },
          }))
        } else if (isAbort(cause) && threadId !== null) {
          void queryClient.invalidateQueries({
            queryKey: chatKeys.messages(threadId),
          })
        } else if (!isAbort(cause) && requestVersion.current === version) {
          // The request to our own backend failed before any SSE frame could
          // classify it (network drop, bad response, etc.) — "unknown" maps
          // to a plain Retry, with no Model setup CTA that wouldn't apply.
          setChatErrors((current) => ({
            ...current,
            [String(assistantId)]: {
              kind: "unknown",
              message: cause instanceof Error ? cause.message : "",
              provider: "",
              retryText: text,
              retryImages: images,
              detailIsLocal: true,
            },
          }))
        }
      } finally {
        if (requestVersion.current === version) {
          setIsRunning(false)
          setAutoNamingThreadId(null)
          // A request outlives its turn only on screen: opencode dropped it.
          setApprovals([])
        }
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
      const failed = chatErrors[assistantId]
      if (!failed) return
      void send(failed.retryText, failed.retryImages)
    },
    [chatErrors, send]
  )

  const cancel = useCallback(async () => {
    streamController.current?.abort()
    setIsRunning(false)
    setAutoNamingThreadId(null)
  }, [])

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
    activeThreadId !== null && !usesLiveMessages && messagesQuery.isPending

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

  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages: threadMessages,
    convertMessage: (message) =>
      toRuntimeMessage(message, chatErrors, activeThreadId),
    adapters,
    onNew,
    isRunning,
    isSendDisabled: !canSend || isLoadingMessages || isLoadingThreads,
    onCancel: cancel,
  })

  const activeThread = useMemo(
    () => threads.find((thread) => thread.id === activeThreadId) ?? null,
    [activeThreadId, threads]
  )

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
