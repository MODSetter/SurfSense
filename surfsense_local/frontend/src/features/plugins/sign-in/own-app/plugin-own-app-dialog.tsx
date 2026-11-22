import { useQueryClient } from "@tanstack/react-query"

import { pluginsQueryKey, signInAgain, type Plugin } from "../../api"
import { connectedToast } from "../../connect-toasts"
import { OwnAppDialog } from "./own-app-dialog"
import type { OwnAppReason } from "./own-app-reason"

/** A saved plugin signed in again as the user's own app; its tool settings stay. */
export function PluginOwnAppDialog({
  plugin,
  reason,
  open,
  onOpenChange,
}: {
  plugin: Plugin
  reason: OwnAppReason
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  return (
    <OwnAppDialog
      plugin={plugin.name}
      reason={reason}
      open={open}
      onOpenChange={onOpenChange}
      start={(app) => signInAgain(plugin.id, app)}
      onConnected={() => {
        onOpenChange(false)
        connectedToast(plugin.name)
        void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
      }}
    />
  )
}
