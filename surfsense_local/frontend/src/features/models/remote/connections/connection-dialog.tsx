import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { intl } from "@/i18n/intl"

import { useRefreshModels } from "../../models-query"
import type { Connection } from "./api"
import { ConnectionForm } from "./connection-form"

/**
 * Adding or editing a server, over whatever page asked. Saving refreshes and
 * closes; a new server is handed to `onCreated`, so the page can open its models.
 */
export function ConnectionDialog({
  open,
  connection,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  /** The server to edit; absent to add one. */
  connection?: Connection
  onOpenChange: (open: boolean) => void
  /** A server just added, whose models are what the user wants next. */
  onCreated?: (connection: Connection) => void
}) {
  const refresh = useRefreshModels()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="select-none sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {connection
              ? intl.formatMessage(
                  { id: "models_connection_dialog_edit_title" },
                  {
                    server: connection.label,
                  }
                )
              : intl.formatMessage({
                  id: "models_connection_dialog_add_title",
                })}
          </DialogTitle>
          <DialogDescription>
            {connection
              ? intl.formatMessage({ id: "models_connection_dialog_edit_body" })
              : intl.formatMessage({ id: "models_connection_dialog_add_body" })}
          </DialogDescription>
        </DialogHeader>
        {/* Mounted per opening, so a closed dialog forgets what was typed. */}
        {open ? (
          <ConnectionForm
            key={connection?.id ?? "new"}
            connection={connection}
            onCancel={() => onOpenChange(false)}
            onSaved={(saved) => {
              void refresh()
              onOpenChange(false)
              if (!connection) onCreated?.(saved)
            }}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
