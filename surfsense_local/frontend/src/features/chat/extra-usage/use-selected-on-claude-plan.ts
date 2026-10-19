import { useConnections } from "@/features/models/remote/connections/use-connections"
import type { ModelSelection } from "@/features/models/selection/api"

/** Whether the chat model now selected is answered by the Claude plan, whose extra usage the notice is about. */
export function useSelectedOnClaudePlan(selection: ModelSelection | null) {
  const { data: connections } = useConnections()
  return (
    selection?.connection_id != null &&
    connections?.some(
      (connection) =>
        connection.id === selection.connection_id &&
        connection.auth_kind === "claude_plan"
    ) === true
  )
}
