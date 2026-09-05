import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react"

import { ApiError } from "@/lib/api"

import {
  createThread,
  deleteThread,
  listMessages,
  listThreads,
  streamMessage,
  type ChatMessage,
  type ChatThread,
} from "./api"
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

function threadTitle(text: string) {
  return (text.split(/\r?\n/, 1)[0].trim() || "New chat").slice(0, 80)
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

export function useChatRuntime({
  workspaceId,
  canSend,
  onCitations,
  onModelRequired,
}: {
  workspaceId: number
  canSend: boolean
  onCitations: (citations: Citation[]) => void
  onModelRequired: () => void
}) {
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loadController = useRef<AbortController | null>(null)
  const streamController = useRef<AbortController | null>(null)
  const requestVersion = useRef(0)

  const acceptMessages = useCallback(
    async (threadId: number, controller: AbortController, version: number) => {
      try {
        const next = await listMessages(threadId, controller.signal)
        if (requestVersion.current === version) {
          setMessages(next)
          const citations =
            [...next].reverse().find((message) => message.role === "assistant")
              ?.content.citations ?? []
          onCitations(citations)
        }
      } catch (cause) {
        if (!isAbort(cause) && requestVersion.current === version) {
          setError(messageFrom(cause))
        }
      } finally {
        if (requestVersion.current === version) {
          setIsLoadingMessages(false)
        }
      }
    },
    [onCitations]
  )

  const selectThread = useCallback(
    (threadId: number) => {
      streamController.current?.abort()
      loadController.current?.abort()
      const controller = new AbortController()
      const version = ++requestVersion.current
      loadController.current = controller
      setActiveThreadId(threadId)
      setMessages([])
      setError(null)
      setIsRunning(false)
      setIsLoadingMessages(true)
      onCitations([])
      void acceptMessages(threadId, controller, version)
    },
    [acceptMessages, onCitations]
  )

  useEffect(() => {
    const controller = new AbortController()
    loadController.current = controller

    void listThreads(workspaceId, controller.signal)
      .then((next) => {
        if (loadController.current !== controller) {
          return
        }
        setThreads(next)
        setIsLoadingThreads(false)
        if (next[0]) {
          selectThread(next[0].id)
        }
      })
      .catch((cause: unknown) => {
        if (!isAbort(cause) && loadController.current === controller) {
          setError(messageFrom(cause))
          setIsLoadingThreads(false)
        }
      })

    return () => {
      loadController.current?.abort()
      streamController.current?.abort()
      requestVersion.current += 1
    }
  }, [selectThread, workspaceId])

  const startNewChat = () => {
    streamController.current?.abort()
    loadController.current?.abort()
    requestVersion.current += 1
    setActiveThreadId(null)
    setMessages([])
    setError(null)
    setIsLoadingMessages(false)
    setIsRunning(false)
    onCitations([])
  }

  const removeThread = async (threadId: number) => {
    try {
      await deleteThread(threadId)
      const next = threads.filter((thread) => thread.id !== threadId)
      setThreads(next)
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

  const onNew = useCallback(
    async (appendMessage: AppendMessage) => {
      const text = submittedText(appendMessage)
      if (!text || isRunning || !canSend) {
        return
      }

      const controller = new AbortController()
      streamController.current?.abort()
      streamController.current = controller
      const version = ++requestVersion.current
      setError(null)
      setIsRunning(true)

      let threadId = activeThreadId
      try {
        if (threadId === null) {
          const thread = await createThread(
            workspaceId,
            threadTitle(text),
            controller.signal
          )
          if (requestVersion.current !== version) {
            return
          }
          threadId = thread.id
          setThreads((current) => [thread, ...current])
          setActiveThreadId(thread.id)
        }

        const timestamp = new Date().toISOString()
        const userId = `optimistic-user-${version}`
        const assistantId = `optimistic-assistant-${version}`
        setMessages((current) => [
          ...current,
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

        await streamMessage(threadId, text, controller.signal, (event) => {
          if (requestVersion.current !== version) {
            return
          }
          if (event.type === "delta") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: {
                        ...message.content,
                        text: (message.content.text ?? "") + event.text,
                      },
                    }
                  : message
              )
            )
          } else if (event.type === "citations") {
            onCitations(event.items)
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      content: { ...message.content, citations: event.items },
                    }
                  : message
              )
            )
          } else if (event.type === "error") {
            setError(event.message)
          }
        })

        if (requestVersion.current === version) {
          const canonical = await listMessages(threadId, controller.signal)
          if (requestVersion.current === version) {
            setMessages(canonical)
          }
        }
      } catch (cause) {
        if (
          cause instanceof ApiError &&
          cause.status === 409 &&
          cause.message.includes("no chat model selected")
        ) {
          onModelRequired()
        } else if (
          isAbort(cause) &&
          requestVersion.current === version &&
          threadId !== null
        ) {
          void listMessages(threadId).then((canonical) => {
            if (requestVersion.current === version) {
              setMessages(canonical)
            }
          })
        } else if (!isAbort(cause) && requestVersion.current === version) {
          setError(messageFrom(cause))
        }
      } finally {
        if (requestVersion.current === version) {
          setIsRunning(false)
        }
      }
    },
    [
      activeThreadId,
      canSend,
      isRunning,
      onCitations,
      onModelRequired,
      workspaceId,
    ]
  )

  const cancel = useCallback(async () => {
    streamController.current?.abort()
    setIsRunning(false)
  }, [])

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
    activeThread,
    activeThreadId,
    messages,
    error,
    isLoadingThreads,
    isLoadingMessages,
    isRunning,
    selectThread,
    startNewChat,
    removeThread,
    clearError: () => setError(null),
  }
}
