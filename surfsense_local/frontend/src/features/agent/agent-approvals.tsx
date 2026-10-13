import type { ReactNode } from "react"

import { AgentApprovalsContext, type AgentApprovals } from "./approvals-context"

/** Hands the open thread's waiting requests to its replies, which ask on the steps they hold back. */
export function AgentApprovalsProvider({
  approvals,
  answer,
  children,
}: AgentApprovals & { children: ReactNode }) {
  return (
    <AgentApprovalsContext.Provider value={{ approvals, answer }}>
      {children}
    </AgentApprovalsContext.Provider>
  )
}
