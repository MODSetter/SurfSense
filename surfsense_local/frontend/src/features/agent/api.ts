import { requestVoid } from "@/lib/api"

/** One tool call the agent made, as `agent-step` frames and `content.steps` carry it. */
export type AgentStep = {
  id: string
  tool: string | null
  status: "pending" | "running" | "completed" | "error"
  title: string | null
  input: Record<string, unknown>
  output?: string
  error?: string
}

/** Something the agent wants to do that waits for the user's answer. */
export type PermissionRequest = {
  id: string
  permission: string
  patterns: string[]
  command: string | null
}

/** The user's answer; there is no "always" (ADR 0028). */
export type PermissionReply = "once" | "reject"

export function answerPermission(
  threadId: number,
  requestId: string,
  reply: PermissionReply
): Promise<void> {
  return requestVoid(
    `/chat/threads/${threadId}/permissions/${encodeURIComponent(requestId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reply }),
    }
  )
}
