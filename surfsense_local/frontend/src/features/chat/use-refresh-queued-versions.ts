import { useQueryClient } from "@tanstack/react-query"

import { useWorkspaceChanges } from "@/features/workspaces/use-workspace-changes"

import type { ChatMessage } from "./api"
import { chatKeys } from "./query-keys"

// The first line a tool writes for a version still being made (rendered_label.py).
const QUEUED = "Queued artifact "

function waitsForAVersion(messages: ChatMessage[]): boolean {
  return messages.some((message) =>
    message.content.steps?.some(
      (step) => !step.artifact && step.output?.startsWith(QUEUED)
    )
  )
}

/**
 * Reads the thread again once an artifact is ready, so a step whose version
 * finished after its reply links to it. A running turn's stream keeps it current.
 */
export function useRefreshQueuedVersions(
  workspaceId: number,
  threadId: number | null,
  running: boolean
) {
  const queryClient = useQueryClient()

  useWorkspaceChanges(workspaceId, "artifacts", (change) => {
    if (threadId === null || running) return
    if (change && change.status !== "ready") return
    const queryKey = chatKeys.messages(threadId)
    const messages = queryClient.getQueryData<ChatMessage[]>(queryKey)
    if (messages && waitsForAVersion(messages)) {
      void queryClient.invalidateQueries({ queryKey })
    }
  })
}
