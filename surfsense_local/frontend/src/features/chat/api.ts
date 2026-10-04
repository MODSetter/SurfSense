import type { AgentStep, SourceScope } from "@/features/agent/api"
import { request, requestJson, requestVoid } from "@/lib/api"

import { parseSseStream, type ChatStreamEvent, type Citation } from "./sse"

export type ChatThread = {
  id: number
  workspace_id: number
  title: string | null
  // The agent answers this thread, chosen when it was opened.
  uses_agent: boolean
  created_at: string
  updated_at: string
}

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
  // An agent turn's sources, on the user's message.
  scope?: SourceScope
  // Client only: what a turn not yet stored shows in place of `images`.
  previews?: string[]
  // Client only: how far the model has read the prompt, while it waits.
  progress?: { processed: number; total: number }
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

export async function streamMessage(
  threadId: number,
  text: string,
  images: ImageUpload[],
  documentIds: number[],
  thinking: boolean,
  signal: AbortSignal,
  onEvent: (event: ChatStreamEvent) => void
): Promise<void> {
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
    }),
    signal,
  })
  if (!response.body) {
    throw new Error("The chat stream did not include a response body.")
  }

  for await (const event of parseSseStream(response.body)) {
    onEvent(event)
  }
}
