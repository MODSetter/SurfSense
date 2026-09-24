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
import { useRefreshModels } from "@/features/models/models-query"
import type { Connection } from "@/features/models/remote/connections/api"
import { ConnectionForm } from "@/features/models/remote/connections/connection-form"
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

type Page =
  { kind: "list" } | { kind: "add" } | { kind: "edit"; connection: Connection }

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
  const refresh = useRefreshModels()
  const [page, setPage] = useState<Page>({ kind: "list" })
  const [openServerId, setOpenServerId] = useState<number | null>(null)
  const back = { label: title, onClick: () => setPage({ kind: "list" }) }
  // Back on the list with the server's group open: its models are next.
  const showServer = (connection: Connection) => {
    void refresh()
    setOpenServerId(connection.id)
    setPage({ kind: "list" })
  }

  if (page.kind === "add") {
    return (
      <SettingsSection
        title={`Add ${slot === "image" ? "an" : "a"} ${slot} model`}
        description="Run one on this computer, or use one from a server you already run."
        back={back}
        scrollable="all"
      >
        <AddModelOptions download={download} onConnected={showServer} />
      </SettingsSection>
    )
  }

  if (page.kind === "edit") {
    return (
      <SettingsSection
        title={`Edit ${page.connection.label}`}
        description="Servers are shared by every model type, so a change here applies to all of them."
        back={back}
        scrollable="all"
      >
        <ConnectionForm
          connection={page.connection}
          onCancel={back.onClick}
          onSaved={showServer}
        />
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
    <Button type="button" size="sm" onClick={() => setPage({ kind: "add" })}>
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
              onDownload={() => setPage({ kind: "add" })}
              onUse={onUse}
              onDelete={onDelete}
            />
          ) : null}

          <ServerModelPicker
            modelType={modelType}
            openServerId={openServerId}
            onEdit={(connection) => setPage({ kind: "edit", connection })}
            onSelected={onSelected}
            onChatCleared={onChatCleared}
          />
        </div>
      )}
    </SettingsSection>
  )
}
