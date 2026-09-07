import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

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
import type { Citation } from "./sse"

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
  return `surfsense-local:last-thread:${workspaceId}:v1`
}

function rememberThread(workspaceId: number, threadId: number | null) {
  try {
    if (threadId === null) {
      localStorage.removeItem(lastThreadKey(workspaceId))
    } else {
      localStorage.setItem(lastThreadKey(workspaceId), String(threadId))
    }
  } catch {
    // Selection remains valid for this session when storage is unavailable.
  }
}

function initialThreadId(workspaceId: number, threads: ChatThread[]) {
  try {
    const stored = Number(localStorage.getItem(lastThreadKey(workspaceId)))
    if (threads.some((thread) => thread.id === stored)) {
      return stored
    }
  } catch {
    // The newest thread below is a safe fallback.
  }
  return threads[0]?.id ?? null
}

function latestCitations(messages: ChatMessage[]) {
  return (
    [...messages].reverse().find((message) => message.role === "assistant")
      ?.content.citations ?? []
  )
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

function toRuntimeMessage(message: ChatMessage): ThreadMessageLike {
  return {
    id: String(message.id),
    role: message.role,
    content: [{ type: "text", text: message.content.text ?? "" }],
    createdAt: new Date(message.created_at),
    metadata: {
      custom: {
        citations: message.content.citations ?? [],
      },
    },
  }
}

export type ConversationView =
  | { status: "initializing" }
  | { status: "new" }
  | { status: "creating" }
  | { status: "active"; threadId: number }

export function useChatRuntime({
  workspaceId,
  canSend,
  selectedDocumentIds,
  onCitations,
  onModelRequired,
}: {
  workspaceId: number
  canSend: boolean
  selectedDocumentIds: number[]
  onCitations: (citations: Citation[]) => void
  onModelRequired: () => void
}) {
  const queryClient = useQueryClient()
  const [selectedView, setConversationView] = useState<ConversationView | null>(
    null
  )
  const [liveMessages, setLiveMessages] = useState<ChatMessage[] | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [autoNamingThreadId, setAutoNamingThreadId] = useState<number | null>(
    null
  )
  const [error, setError] = useState<string | null>(null)
  const streamController = useRef<AbortController | null>(null)
  const requestVersion = useRef(0)

  const threadsQuery = useQuery({
    queryKey: chatKeys.threads(workspaceId),
    queryFn: ({ signal }) => listThreads(workspaceId, signal),
  })
  const threads = threadsQuery.data ?? EMPTY_THREADS
  const initialView = useMemo<ConversationView>(() => {
    if (!threadsQuery.isSuccess) {
      return { status: "initializing" }
    }
    const threadId = initialThreadId(workspaceId, threads)
    return threadId === null
      ? { status: "new" }
      : { status: "active", threadId }
  }, [threads, threadsQuery.isSuccess, workspaceId])
  const conversationView = selectedView ?? initialView
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

  useEffect(() => {
    if (!usesLiveMessages) {
      onCitations(latestCitations(persistedMessages))
    }
  }, [onCitations, persistedMessages, usesLiveMessages])

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
      setError(null)
      setIsRunning(false)
      setAutoNamingThreadId(null)
      onCitations([])
    },
    [activeThreadId, onCitations, workspaceId]
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
    setError(null)
    setIsRunning(false)
    setAutoNamingThreadId(null)
    onCitations([])
  }, [onCitations, workspaceId])

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
      setError(messageFrom(cause))
    }
  }

  const rename = async (threadId: number, title: string) => {
    setError(null)
    try {
      const renamed = await renameThreadMutation.mutateAsync({
        threadId,
        title,
      })
      queryClient.setQueryData<ChatThread[]>(
        chatKeys.threads(workspaceId),
        (current = []) =>
          current.map((thread) => (thread.id === renamed.id ? renamed : thread))
      )
      return true
    } catch (cause) {
      setError(messageFrom(cause))
      return false
    }
  }

  const onNew = useCallback(
    async (appendMessage: AppendMessage) => {
      const text = submittedText(appendMessage)
      if (
        !text ||
        isRunning ||
        !canSend ||
        conversationView.status === "initializing" ||
        conversationView.status === "creating"
      ) {
        return
      }

      const controller = new AbortController()
      streamController.current?.abort()
      streamController.current = controller
      const version = ++requestVersion.current
      setError(null)
      setIsRunning(true)

      let threadId =
        conversationView.status === "active" ? conversationView.threadId : null
      let userMessageId: number | null = null
      let assistantMessageId: number | null = null
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

        const timestamp = new Date().toISOString()
        let userId: number | string = `optimistic-user-${version}`
        let assistantId: number | string = `optimistic-assistant-${version}`
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
            created_at: timestamp,
          },
          {
            id: assistantId,
            role: "assistant",
            content: { text: "", citations: [] },
            created_at: timestamp,
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
                      return { ...message, id: nextUserId }
                    }
                    if (message.id === previousAssistantId) {
                      return { ...message, id: nextAssistantId }
                    }
                    return message
                  }) ?? null
              )
            } else if (event.type === "thread-title-update") {
              setAutoNamingThreadId(null)
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
            } else if (event.type === "citations") {
              onCitations(event.items)
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
            } else if (event.type === "error") {
              setError(event.message)
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
          setError(messageFrom(cause))
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
      onCitations,
      onModelRequired,
      queryClient,
      selectedDocumentIds,
      workspaceId,
    ]
  )

  const cancel = useCallback(async () => {
    streamController.current?.abort()
    setIsRunning(false)
    setAutoNamingThreadId(null)
  }, [])

  const isLoadingThreads = threadsQuery.isPending
  const isLoadingMessages =
    activeThreadId !== null && !usesLiveMessages && messagesQuery.isPending
  const queryError = threadsQuery.error ?? messagesQuery.error
  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages,
    convertMessage: toRuntimeMessage,
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
    error: error ?? (queryError ? messageFrom(queryError) : null),
    isLoadingThreads,
    isLoadingMessages,
    isRunning,
    autoNamingThreadId,
    selectThread,
    startNewChat,
    rename,
    removeThread,
    clearError: () => setError(null),
  }
}
