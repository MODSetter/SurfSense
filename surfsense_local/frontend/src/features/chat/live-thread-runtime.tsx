import {
  useCallback,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react"
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ExternalStoreAdapter,
} from "@assistant-ui/react"

import type { ChatMessage } from "./api"
import { liveRun, subscribeToRuns } from "./runs/run-store"
import { composedThread, toRuntimeMessage } from "./thread-messages"

/** What the open thread's runtime is built from, besides its run. */
export type LiveThreadSource = {
  threadId: number | null
  persistedMessages: ChatMessage[]
  adapters: ExternalStoreAdapter<ChatMessage>["adapters"]
  isSendDisabled: boolean
  onNew: (message: AppendMessage) => Promise<void>
  onCancel: () => Promise<void>
}

const NO_IDS: ReadonlyArray<number | string> = []

/**
 * The open thread's runtime, fed every frame of its run. It is the only part
 * of the page a frame renders: `children` is the same element then, so React
 * skips it, and each message re-renders from its own state or not at all.
 */
export function LiveThreadRuntime({
  threadId,
  persistedMessages,
  adapters,
  isSendDisabled,
  onNew,
  onCancel,
  children,
}: LiveThreadSource & { children: ReactNode }) {
  // Another thread's frames leave this run as it was, and render nothing.
  const run = useSyncExternalStore(subscribeToRuns, () => liveRun(threadId))
  const pair = run?.pair ?? null
  const replaces = run?.replaces ?? NO_IDS
  const messages = useMemo(
    () => composedThread(persistedMessages, pair, replaces),
    [persistedMessages, pair, replaces]
  )
  const latestAssistantId = useMemo(() => {
    const latest = messages.findLast((message) => message.role === "assistant")
    return latest ? String(latest.id) : null
  }, [messages])
  // Held between frames: a new converter has assistant-ui convert, and
  // re-render, every message of the thread again.
  const convertMessage = useCallback(
    (message: ChatMessage) =>
      toRuntimeMessage(message, latestAssistantId, threadId),
    [latestAssistantId, threadId]
  )
  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages,
    convertMessage,
    adapters,
    onNew,
    isRunning: run !== null && !run.ended,
    isSendDisabled,
    onCancel,
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
