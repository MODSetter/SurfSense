import { request, requestJson, requestVoid } from "@/lib/api"

import { parseSseStream, type ChatStreamEvent, type Citation } from "./sse"

export type ChatThread = {
  id: number
  workspace_id: number
  title: string | null
  created_at: string
  updated_at: string
}

export type MessageContent = {
  text?: string
  citations?: Citation[]
}

export type ChatMessage = {
  id: number | string
  role: "user" | "assistant" | "system"
  content: MessageContent
  created_at: string
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

export async function streamMessage(
  threadId: number,
  text: string,
  signal: AbortSignal,
  onEvent: (event: ChatStreamEvent) => void
): Promise<void> {
  const response = await request(`/chat/threads/${threadId}/messages`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
    signal,
  })
  if (!response.body) {
    throw new Error("The chat stream did not include a response body.")
  }

  for await (const event of parseSseStream(response.body)) {
    onEvent(event)
  }
}
