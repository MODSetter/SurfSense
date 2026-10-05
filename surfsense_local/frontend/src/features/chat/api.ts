import type { AgentStep } from "@/features/agent/api"
import { request, requestJson, requestVoid } from "@/lib/api"

import {
  parseNumberedSseStream,
  type ChatErrorKind,
  type Citation,
  type NumberedEvent,
} from "./sse"

export type ChatThread = {
  id: number
  workspace_id: number
  title: string | null
  // The agent answers this thread, chosen when it was opened.
  uses_agent: boolean
  created_at: string
  updated_at: string
  // A reply is being generated for it right now. Absent on a thread the
  // client made itself before the list was read again.
  running?: boolean
}

/** How a stored reply ended; absent for one that completed. */
export type TurnEnding =
  | {
      type: "error"
      kind: ChatErrorKind
      message: string
      provider?: string
      // Client only: our own request failed before the API could classify it.
      local?: boolean
    }
  | { type: "stopped" }
  | { type: "interrupted" }

/** An image a stored turn carried; the bytes are served by the image route. */
export type StoredImage = {
  key: string
  mime: string
  size_bytes: number
  sha256: string
}

/** One attached image as the send request carries it. `mime` is advisory. */
export type ImageUpload = { mime: string | null; data: string }

export type MessageContent = {
  text?: string
  citations?: Citation[]
  // A thinking model's trace, shown folded above the answer.
  reasoning?: { text: string; duration_ms: number | null }
  images?: StoredImage[]
  // An agent reply's tool calls, in the order it made them.
  steps?: AgentStep[]
  // Client only: what a turn not yet stored shows in place of `images`.
  previews?: string[]
  // Client only: how far the model has read the prompt, while it waits.
  progress?: { processed: number; total: number }
  ending?: TurnEnding
  // Client only: the reply's place in line for the local runtime.
  queue?: { position: number }
}

export type ChatMessage = {
  id: number | string
  role: "user" | "assistant" | "system"
  content: MessageContent
  created_at: string | null
  completed_at: string | null
}

export function listThreads(
  workspaceId: number,
  signal?: AbortSignal
): Promise<ChatThread[]> {
  return requestJson<ChatThread[]>(`/workspaces/${workspaceId}/chat/threads`, {
    signal,
  })
}

export function createThread(
  workspaceId: number,
  title: string,
  signal?: AbortSignal
): Promise<ChatThread> {
  return requestJson<ChatThread>(`/workspaces/${workspaceId}/chat/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
    signal,
  })
}

export function listMessages(
  threadId: number,
  signal?: AbortSignal
): Promise<ChatMessage[]> {
  return requestJson<ChatMessage[]>(`/chat/threads/${threadId}/messages`, {
    signal,
  })
}

export function deleteThread(
  threadId: number,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/chat/threads/${threadId}`, {
    method: "DELETE",
    signal,
  })
}

export function renameThread(
  threadId: number,
  title: string,
  signal?: AbortSignal
): Promise<ChatThread> {
  return requestJson<ChatThread>(`/chat/threads/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
    signal,
  })
}

export async function* streamMessage(
  threadId: number,
  text: string,
  images: ImageUpload[],
  documentIds: number[],
  thinking: boolean,
  retryOf: number | null,
  signal: AbortSignal
): AsyncGenerator<NumberedEvent> {
  const response = await request(`/chat/threads/${threadId}/messages`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      document_ids: documentIds,
      // Only when there are some, so a text turn sends exactly what it did.
      ...(images.length > 0 ? { images } : {}),
      // Only when off, for the same reason: on is the API's default.
      ...(thinking ? {} : { thinking: false }),
      ...(retryOf !== null ? { retry_of: retryOf } : {}),
    }),
    signal,
  })
  if (!response.body) {
    throw new Error("The chat stream did not include a response body.")
  }
  yield* parseNumberedSseStream(response.body)
}

/** A thread's running reply, replayed after frame `after` and then live. */
export async function* followRun(
  threadId: number,
  after: number,
  signal: AbortSignal
): AsyncGenerator<NumberedEvent> {
  const response = await request(
    `/chat/threads/${threadId}/run?after=${after}`,
    { headers: { Accept: "text/event-stream" }, signal }
  )
  if (!response.body) return
  yield* parseNumberedSseStream(response.body)
}

/** End a thread's reply where it is; the API stores what it has. */
export function stopRun(threadId: number): Promise<void> {
  return requestVoid(`/chat/threads/${threadId}/run/stop`, { method: "POST" })
}
