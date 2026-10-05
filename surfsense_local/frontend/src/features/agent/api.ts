import { requestVoid } from "@/lib/api"

/** The Studio artifact a `surfsense_render_document` call made, once that
 *  version is ready. */
export type RenderedArtifact = {
  id: number
  title: string
  version: number
  /** True when no earlier version of the document is ready, since a failed
   *  run uses up a number. Absent from a backend that does not say; the
   *  version being the first then stands in. */
  created?: boolean
}

/** One tool call the agent made, as `agent-step` frames and `content.steps` carry it. */
export type AgentStep = {
  id: string
  tool: string | null
  status: "pending" | "running" | "completed" | "error"
  title: string | null
  input: Record<string, unknown>
  output?: string
  error?: string
  /** Set only once a render's version is ready: null while it runs and
   *  when its script failed, though the failed version exists. Absent on
   *  every other tool. */
  artifact?: RenderedArtifact | null
}

/** The sources an agent turn was allowed to use: those ticked when it was
 *  sent, each id beside its title. Absent when the turn named no selection,
 *  which gives the agent the whole workspace. */
export type TurnSources = {
  document_ids: number[]
  titles: string[]
  /** Set, with no ids or titles, when the turn had too many sources to tag
   *  each one (more than 200). */
  count?: number
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
