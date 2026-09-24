import { useState } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import type { Connection } from "@/features/models/remote/connections/api"
import { ConnectionDialog } from "@/features/models/remote/connections/connection-dialog"
import { useConnections } from "@/features/models/remote/connections/use-connections"
import { ServerModelPicker } from "@/features/models/remote/models/server-model-picker"
import { intl } from "@/i18n/intl"

import type { OnboardingSlot } from "./slot"

/**
 * A model from a server, in Settings' own server groups. Connecting and
 * editing happen in Settings' dialog; a server just added opens on its models.
 */
export function ServerPath({
  modelType,
  openServerId: initialOpenServerId,
}: {
  modelType: OnboardingSlot
  /** A server added before this page opened, whose models to show first. */
  openServerId: number | null
}) {
  const connections = useConnections()
  const [dialog, setDialog] = useState<Connection | "new" | null>(null)
  const [openServerId, setOpenServerId] = useState(initialOpenServerId)

  if (connections.isPending) return null
  const servers = connections.data ?? []

  return (
    <div className="flex flex-col gap-5">
      {servers.length ? (
        <ServerModelPicker
          modelType={modelType}
          openServerId={openServerId}
          onEdit={setDialog}
        />
      ) : (
        <p className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "onboarding_server_path_empty",
            defaultMessage: "No servers connected yet.",
          })}
        </p>
      )}
      <Button
        type="button"
        variant="ghost"
        className="self-start"
        onClick={() => setDialog("new")}
      >
        <PlusIcon data-icon="inline-start" />
        {servers.length
          ? intl.formatMessage({
              id: "onboarding_server_path_connect_another_button",
              defaultMessage: "Connect another server",
            })
          : intl.formatMessage({
              id: "onboarding_server_path_connect_button",
              defaultMessage: "Connect a server",
            })}
      </Button>
      <ConnectionDialog
        open={dialog !== null}
        connection={dialog !== null && dialog !== "new" ? dialog : undefined}
        onOpenChange={(open) => {
          if (!open) setDialog(null)
        }}
        onCreated={(connection) => setOpenServerId(connection.id)}
      />
    </div>
  )
}
