import { createContext, useContext } from "react"

import type { PermissionReply, PermissionRequest } from "./api"

export type AgentApprovals = {
  /** The open thread's requests waiting on the user, oldest first. */
  approvals: PermissionRequest[]
  answer: (request: PermissionRequest, reply: PermissionReply) => Promise<void>
}

export const AgentApprovalsContext = createContext<AgentApprovals>({
  approvals: [],
  answer: async () => {},
})

export function useAgentApprovals() {
  return useContext(AgentApprovalsContext)
}
