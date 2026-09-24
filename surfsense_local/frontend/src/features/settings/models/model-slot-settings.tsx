import { useState, type ReactNode } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { CircleAlertIcon } from "@/components/ui/icons"
import { AddModelOptions } from "@/features/models/add-model/add-model-options"
import type { ModelType } from "@/features/models/model-type"
import type { Connection } from "@/features/models/remote/connections/api"
import { ConnectionDialog } from "@/features/models/remote/connections/connection-dialog"
import { useConnections } from "@/features/models/remote/connections/use-connections"
import { ServerModelPicker } from "@/features/models/remote/models/server-model-picker"
import type { ModelSelection } from "@/features/models/selection/api"
import { InUseSummary } from "@/features/models/your-models/in-use-summary"
import { LocalModelsGroup } from "@/features/models/your-models/local-models-group"
import type {
  YourModelRow,
  YourModels,
} from "@/features/models/your-models/your-model-row"

import { SettingsSection } from "../settings-section"

type Page = "list" | "add"

/**
 * One slot's settings: the model in use, then every source as a group. Adding
 * a model and editing a server are pages with a way back, never dialogs.
 */
export function ModelSlotSettings({
  title,
  description,
  slot,
  modelType,
  models,
  pending,
  download,
  onUse,
  onDelete,
  onSelected,
  onChatCleared,
}: {
  title: string
  description: string
  slot: string
  modelType: ModelType
  models: YourModels
  pending?: ReactNode
  download: ReactNode
  onUse: (row: YourModelRow) => Promise<unknown>
  onDelete: (row: YourModelRow) => Promise<unknown>
  onSelected?: (selection: ModelSelection) => void
  onChatCleared?: () => void
}) {
  const connections = useConnections()
  const [page, setPage] = useState<Page>("list")
  // Edited in a dialog over the list; saving leaves the list as it was.
  const [editing, setEditing] = useState<Connection | null>(null)
  // A server just added: back on the list with its models open, since
  // choosing one of them is why it was added.
  const [openServerId, setOpenServerId] = useState<number | null>(null)
  const showNewServer = (connection: Connection) => {
    setOpenServerId(connection.id)
    setPage("list")
  }
  const back = { label: title, onClick: () => setPage("list") }

  if (page === "add") {
    return (
      <SettingsSection
        title={`Add ${/^[aeiou]/.test(slot) ? "an" : "a"} ${slot} model`}
        description="Run one on this computer, or use one from a server you already run."
        back={back}
        scrollable="all"
      >
        <AddModelOptions download={download} onConnected={showNewServer} />
      </SettingsSection>
    )
  }

  const empty =
    !models.isPending &&
    connections.data?.length === 0 &&
    models.local.length === 0 &&
    !pending &&
    models.inUse === null
  const add = (
    <Button type="button" size="sm" onClick={() => setPage("add")}>
      Add model
    </Button>
  )

  return (
    <SettingsSection title={title} description={description} scrollable="all">
      {models.error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>Could not load model settings</AlertTitle>
          <AlertDescription>{models.error.message}</AlertDescription>
        </Alert>
      ) : models.isPending ? null : empty ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>No {slot} model yet</EmptyTitle>
            <EmptyDescription>
              {models.canDownload
                ? "Download one to run on this computer, or use one from a server you already run."
                : "Use one from a server you already run."}
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>{add}</EmptyContent>
        </Empty>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between gap-3">
            <InUseSummary slot={slot} inUse={models.inUse} />
            {add}
          </div>

          {models.canDownload || models.local.length > 0 || pending ? (
            <LocalModelsGroup
              rows={models.local}
              pending={pending}
              onDownload={() => setPage("add")}
              onUse={onUse}
              onDelete={onDelete}
            />
          ) : null}

          <ServerModelPicker
            modelType={modelType}
            openServerId={openServerId}
            onEdit={setEditing}
            onSelected={onSelected}
            onChatCleared={onChatCleared}
          />
        </div>
      )}
      <ConnectionDialog
        open={editing !== null}
        connection={editing ?? undefined}
        onOpenChange={(open) => {
          if (!open) setEditing(null)
        }}
      />
    </SettingsSection>
  )
}
