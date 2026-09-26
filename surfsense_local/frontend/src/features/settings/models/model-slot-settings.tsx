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
import { intl } from "@/i18n/intl"

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
  servers = true,
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
  /** Off where no server model can do the slot's job yet. */
  servers?: boolean
}) {
  const connections = useConnections()
  const [page, setPage] = useState<Page>("list")
  // Edited in a dialog over the list; saving leaves the list as it was.
  const [editing, setEditing] = useState<Connection | null>(null)
  const [editOpen, setEditOpen] = useState(false)
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
        title={intl.formatMessage(
          {
            id: "settings_models_add_page_title",
            defaultMessage:
              "{slot, select, audio {Add an audio model} chat {Add a chat model} image {Add an image model} image_edit {Add an image editing model} video {Add a video model} other {Add a model}}",
          },
          { slot }
        )}
        description={
          servers
            ? intl.formatMessage({
                id: "settings_models_add_page_body",
                defaultMessage:
                  "Run one on this computer, or use one from a server you already run.",
              })
            : undefined
        }
        back={back}
        scrollable="all"
      >
        <AddModelOptions
          download={download}
          onConnected={servers ? showNewServer : undefined}
        />
      </SettingsSection>
    )
  }

  const empty =
    !models.isPending &&
    (!servers || connections.data?.length === 0) &&
    models.local.length === 0 &&
    !pending &&
    models.inUse === null
  const add = (
    <Button type="button" size="sm" onClick={() => setPage("add")}>
      {intl.formatMessage({
        id: "settings_models_add_button",
        defaultMessage: "Add model",
      })}
    </Button>
  )

  return (
    <SettingsSection title={title} description={description} scrollable="all">
      {models.error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>
            {intl.formatMessage({
              id: "settings_models_load_error",
              defaultMessage: "Could not load model settings",
            })}
          </AlertTitle>
          <AlertDescription>{models.error.message}</AlertDescription>
        </Alert>
      ) : models.isPending ? null : empty ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>
              {intl.formatMessage(
                {
                  id: "settings_models_empty",
                  defaultMessage:
                    "{slot, select, audio {No audio model yet} chat {No chat model yet} image {No image model yet} image_edit {No image editing model yet} video {No video model yet} other {No model yet}}",
                },
                { slot }
              )}
            </EmptyTitle>
            {servers ? (
              <EmptyDescription>
                {models.canDownload
                  ? intl.formatMessage({
                      id: "settings_models_empty_download_body",
                      defaultMessage:
                        "Download one to run on this computer, or use one from a server you already run.",
                    })
                  : intl.formatMessage({
                      id: "settings_models_empty_server_body",
                      defaultMessage: "Use one from a server you already run.",
                    })}
              </EmptyDescription>
            ) : null}
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

          {servers ? (
            <ServerModelPicker
              modelType={modelType}
              openServerId={openServerId}
              onEdit={(connection) => {
                setEditing(connection)
                setEditOpen(true)
              }}
              onSelected={onSelected}
              onChatCleared={onChatCleared}
            />
          ) : null}
        </div>
      )}
      <ConnectionDialog
        open={editOpen}
        connection={editing ?? undefined}
        onOpenChange={setEditOpen}
        onOpenChangeComplete={(open) => {
          if (!open) setEditing(null)
        }}
      />
    </SettingsSection>
  )
}
