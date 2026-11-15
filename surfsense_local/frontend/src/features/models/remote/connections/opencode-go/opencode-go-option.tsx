import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { OpencodeIcon } from "@/components/ui/opencode-icon"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { ModelType } from "../../../model-type"
import { useRefreshModels } from "../../../models-query"
import { getRemoteProviders, type Connection } from "../api"
import { ConnectionForm } from "../connection-form"
import { useConnectionsServing } from "../use-connections"

const OPENCODE_GO_PROVIDER = "opencode-go"

/**
 * An OpenCode Go plan, offered beside Use a server where people look for a
 * subscription. It is still a server with a Console key, the only sign-in
 * OpenCode documents, so the row opens the server form with Go chosen.
 */
export function OpencodeGoOption({
  modelType,
  onConnected,
  dense = false,
}: {
  modelType: ModelType
  onConnected: (connection: Connection) => void
  /** Onboarding's smaller heading and button, beside its own server row. */
  dense?: boolean
}) {
  // The form's own list and key, so opening it needs no second request.
  const providers = useQuery({
    queryKey: ["remote-providers"],
    queryFn: ({ signal }) => getRemoteProviders(signal),
    staleTime: Infinity,
  })
  const connections = useConnectionsServing(modelType)
  const refresh = useRefreshModels()
  const [open, setOpen] = useState(false)

  const go = providers.data?.find((entry) => entry.id === OPENCODE_GO_PROVIDER)
  if (!go || go.connect.status === "unreachable" || !go.type_counts[modelType])
    return null

  // Any Go server counts, however it was added.
  const connected = connections.data?.find(
    (connection) => connection.catalog_provider === OPENCODE_GO_PROVIDER
  )
  const size = dense ? "default" : "sm"
  const title = intl.formatMessage({
    id: "models_opencode_go_option_title",
    defaultMessage: "Use your OpenCode Go plan",
  })

  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <div
        className={cn(
          "flex justify-between",
          dense ? "items-center gap-4" : "items-start gap-3"
        )}
      >
        <div className="min-w-0">
          <h3
            className={cn(
              "flex items-center gap-2 font-medium",
              dense ? "text-sm" : "text-base"
            )}
          >
            <OpencodeIcon aria-hidden="true" className="size-4" />
            {title}
          </h3>
          {/* pl-6: the icon's 16px plus the 8px gap, so it lines up with the heading text. */}
          <p className="truncate pl-6 text-xs text-muted-foreground">
            {connected
              ? intl.formatMessage(
                  {
                    id: "models_opencode_go_option_connected_body",
                    defaultMessage: "Connected as {server}",
                  },
                  { server: connected.label }
                )
              : intl.formatMessage({
                  id: "models_opencode_go_option_body",
                  defaultMessage: "With a key from the OpenCode Console.",
                })}
          </p>
        </div>
        {connected ? (
          <Button
            type="button"
            size={size}
            variant="outline"
            onClick={() => onConnected(connected)}
          >
            {intl.formatMessage({
              id: "models_opencode_go_option_show_button",
              defaultMessage: "Show models",
            })}
          </Button>
        ) : (
          <Button
            type="button"
            size={size}
            variant="outline"
            onClick={() => setOpen(true)}
          >
            {intl.formatMessage({
              id: "models_opencode_go_option_connect_button",
              defaultMessage: "Connect",
            })}
          </Button>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="select-none sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage({
                id: "models_opencode_go_dialog_title",
                defaultMessage: "Connect OpenCode Go",
              })}
            </DialogTitle>
            <DialogDescription>
              {intl.formatMessage({
                id: "models_opencode_go_dialog_body",
                defaultMessage:
                  "Paste an API key from the OpenCode Console to use your plan’s models.",
              })}
            </DialogDescription>
          </DialogHeader>
          <ConnectionForm
            startWithProvider={OPENCODE_GO_PROVIDER}
            onCancel={() => setOpen(false)}
            onSaved={(connection) => {
              setOpen(false)
              void refresh()
              void connections.refetch()
              onConnected(connection)
            }}
          />
        </DialogContent>
      </Dialog>
    </section>
  )
}
