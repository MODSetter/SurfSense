import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError } from "@/lib/api"

import {
  createThread,
  deleteThread,
  listMessages,
  listThreads,
  renameThread,
  streamMessage,
  type ChatMessage,
  type ChatThread,
} from "./api"
import { chatKeys } from "./query-keys"
import type { ChatErrorKind } from "./sse"

export type ChatTurnError = {
  kind: ChatErrorKind
  message: string
  provider: string
  retryText: string
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
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
  messages: ChatMessage[],
  userMessageId: number,
  assistantMessageId: number
) {
  const ids = new Set(messages.map((message) => message.id))
  return ids.has(userMessageId) && ids.has(assistantMessageId)
}

function areLiveMessagesPersisted(
  liveMessages: ChatMessage[],
  persistedMessages: ChatMessage[]
) {
  const persistedIds = new Set(persistedMessages.map((message) => message.id))
  return liveMessages.every(
    (message) => typeof message.id === "number" && persistedIds.has(message.id)
  )
}

function toRuntimeMessage(
  message: ChatMessage,
  chatErrors: Record<string, ChatTurnError>
): ThreadMessageLike {
  const value =
    message.role === "assistant" ? message.completed_at : message.created_at
  // SQLite stores CURRENT_TIMESTAMP in UTC but returns it without an offset.
  const timestamp =
    value && !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? `${value}Z` : value
  const error = message.role === "assistant" ? chatErrors[String(message.id)] : undefined
  return {
    id: String(message.id),
    role: message.role,
    content: [{ type: "text", text: message.content.text ?? "" }],
    ...(timestamp ? { createdAt: new Date(timestamp) } : {}),
    ...(error
      ? { status: { type: "incomplete", reason: "error", error } as const }
      : {}),
    metadata: {
      custom: {
        citations: message.content.citations ?? [],
      },
    },
  }
}

export function useChatRuntime({
  workspaceId,
  canSend,
  selectedDocumentIds,
  onModelRequired,
}: {
  workspaceId: number
  canSend: boolean
  selectedDocumentIds: number[]
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
  const messages = usesLiveMessages ? liveMessages : persistedMessages

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
      toast.error("Couldn’t delete chat", { description: messageFrom(cause) })
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
      toast.error("Couldn’t rename chat", { description: messageFrom(cause) })
      return false
    }
  }

  const send = useCallback(
    async (text: string) => {
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
      let userMessageId: number | null = null
      let assistantMessageId: number | null = null
      // Declared here (not inside the try) so the catch block below can still
      // attach a failure to the right message, whether or not "accepted" ever
      // remapped these to real ids.
      let userId: number | string = `optimistic-user-${version}`
      let assistantId: number | string = `optimistic-assistant-${version}`
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
            content: { text },
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
          selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined,
          controller.signal,
          (event) => {
            if (requestVersion.current !== version) {
              return
            }
            if (event.type === "accepted") {
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
            } else if (event.type === "error") {
              const failedId = assistantId
              setChatErrors((current) => ({
                ...current,
                [String(failedId)]: {
                  kind: event.kind,
                  message: event.message,
                  provider: event.provider,
                  retryText: text,
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
              message: messageFrom(cause),
              provider: "",
              retryText: text,
            },
          }))
        }
      } finally {
        if (requestVersion.current === version) {
          setIsRunning(false)
          setAutoNamingThreadId(null)
        }
      }
    },
    [
      canSend,
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
    (appendMessage: AppendMessage) => send(submittedText(appendMessage)),
    [send]
  )

  const retry = useCallback(
    (assistantId: string) => {
      const failed = chatErrors[assistantId]
      if (!failed) return
      void send(failed.retryText)
    },
    [chatErrors, send]
  )

  const cancel = useCallback(async () => {
    streamController.current?.abort()
    setIsRunning(false)
    setAutoNamingThreadId(null)
  }, [])

  const finishTitleAnimation = useCallback(() => {
    setAnimatingTitleThreadId(null)
  }, [])

  const isLoadingThreads = threadsQuery.isPending
  const isLoadingMessages =
    activeThreadId !== null && !usesLiveMessages && messagesQuery.isPending

  useEffect(() => {
    if (threadsQuery.error) {
      toast.error("Couldn’t load your chats", {
        description: messageFrom(threadsQuery.error),
      })
    }
  }, [threadsQuery.error])

  useEffect(() => {
    if (messagesQuery.error) {
      toast.error("Couldn’t load this chat", {
        description: messageFrom(messagesQuery.error),
      })
    }
  }, [messagesQuery.error])

  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages,
    convertMessage: (message) => toRuntimeMessage(message, chatErrors),
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
    messages,
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
  }
}
