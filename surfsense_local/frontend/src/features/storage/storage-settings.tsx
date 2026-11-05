import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { MoveConfirmDialog } from "./move-confirm-dialog"
import type { StorageFolder, StorageKind } from "./storage-types"
import { useMoveFlow } from "./use-move-flow"
import { useStorageState } from "./use-storage-state"

function FolderRow({
  kind,
  folder,
  title,
  body,
  planning,
  onChange,
  onUseDefault,
}: {
  kind: StorageKind
  folder: StorageFolder
  title: string
  body: string
  planning: StorageKind | null
  onChange: (kind: StorageKind) => void
  onUseDefault: (kind: StorageKind) => void
}) {
  const busy = planning !== null
  return (
    <div className="flex items-start justify-between gap-8 not-first:mt-8">
      <div className="flex min-w-0 flex-col gap-1">
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="text-sm text-pretty text-muted-foreground">{body}</p>
        <code className="text-sm break-all">{folder.path}</code>
        {folder.connected ? null : (
          <p className="text-sm text-destructive">
            {intl.formatMessage({
              id: "storage_not_connected_label",
              defaultMessage: "This drive isn’t connected.",
            })}
          </p>
        )}
        {folder.freeBytes === null ? null : (
          <p className="text-sm text-muted-foreground tabular-nums">
            {intl.formatMessage(
              {
                id: "storage_free_label",
                defaultMessage:
                  "{free, number, ::unit/gigabyte .#} free on this drive",
              },
              { free: folder.freeBytes / 1e9 }
            )}
          </p>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={busy || !folder.connected}
          onClick={() => onChange(kind)}
        >
          {planning === kind ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "storage_change_button",
            defaultMessage: "Change…",
          })}
        </Button>
        {folder.isDefault ? null : (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy || !folder.connected}
            onClick={() => onUseDefault(kind)}
          >
            {intl.formatMessage({
              id: "storage_default_button",
              defaultMessage: "Move back to default",
            })}
          </Button>
        )}
      </div>
    </div>
  )
}

export function StorageSettings() {
  const { data: state } = useStorageState()
  const flow = useMoveFlow()

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "storage_settings_title",
        defaultMessage: "Storage",
      })}
      description={intl.formatMessage({
        id: "storage_settings_body",
        defaultMessage: "Choose which drive SurfSense keeps its files on.",
      })}
      scrollable="all"
    >
      {state ? (
        <>
          <FolderRow
            kind="models"
            folder={state.models}
            title={intl.formatMessage({
              id: "storage_models_title",
              defaultMessage: "Models",
            })}
            body={intl.formatMessage({
              id: "storage_models_body",
              defaultMessage: "The local models you download.",
            })}
            planning={flow.planning}
            onChange={flow.choose}
            onUseDefault={flow.useDefault}
          />
          <FolderRow
            kind="data"
            folder={state.data}
            title={intl.formatMessage({
              id: "storage_data_title",
              defaultMessage: "All data",
            })}
            body={intl.formatMessage({
              id: "storage_data_body",
              defaultMessage:
                "Workspaces, chats, uploads and the search index, and your models unless you moved them separately.",
            })}
            planning={flow.planning}
            onChange={flow.choose}
            onUseDefault={flow.useDefault}
          />
        </>
      ) : null}
      <MoveConfirmDialog
        ready={flow.ready}
        onConfirm={flow.confirm}
        onDismiss={flow.dismiss}
      />
    </SettingsSection>
  )
}
