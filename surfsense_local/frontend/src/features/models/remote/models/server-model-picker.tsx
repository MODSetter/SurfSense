import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { CircleAlertIcon } from "@/components/ui/icons"

import type { ModelType } from "../../model-type"
import type { ModelSelection } from "../../selection/api"
import type { Connection } from "../connections/api"
import { useConnections } from "../connections/use-connections"
import { ServerModels } from "./server-models"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not load servers"
}

/**
 * One group per OpenAI-compatible server, each offering its models for one
 * slot. Servers are shared across slots; only the models listed are filtered.
 */
export function ServerModelPicker({
  modelType,
  disabled = false,
  openServerId = null,
  onEdit,
  onSelected,
  onChatCleared,
}: {
  modelType: ModelType
  disabled?: boolean
  /** A server just added, whose models are the next thing to pick from. */
  openServerId?: number | null
  onEdit: (connection: Connection) => void
  onSelected?: (selection: ModelSelection) => void
  onChatCleared?: () => void
}) {
  const connections = useConnections()

  if (connections.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Could not load servers</AlertTitle>
        <AlertDescription>{messageFrom(connections.error)}</AlertDescription>
      </Alert>
    )
  }

  return (connections.data ?? []).map((connection) => (
    <ServerModels
      key={connection.id}
      connection={connection}
      modelType={modelType}
      disabled={disabled}
      defaultOpen={connection.id === openServerId}
      onEdit={() => onEdit(connection)}
      onSelected={onSelected}
      onChatCleared={onChatCleared}
    />
  ))
}
