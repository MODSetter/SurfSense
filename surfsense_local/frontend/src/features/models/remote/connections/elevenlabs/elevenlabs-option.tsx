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
import { AudioWaveformIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { ModelType } from "../../../model-type"
import { useRefreshModels } from "../../../models-query"
import type { Connection } from "../api"
import { useConnectionsServing } from "../use-connections"
import { elevenLabsOptionQueryKey, getElevenLabsOption } from "./api"
import { ElevenLabsForm } from "./elevenlabs-form"
import { elevenLabsKeyBody } from "./key-body"

/**
 * ElevenLabs' own API, offered beside Use a server rather than in its provider
 * list, because it does not speak the OpenAI API. Shown only where the backend
 * says it fills the slot; one already connected opens its models instead.
 */
export function ElevenLabsOption({
  modelType,
  onConnected,
}: {
  modelType: ModelType
  onConnected: (connection: Connection) => void
}) {
  const option = useQuery({
    queryKey: elevenLabsOptionQueryKey,
    queryFn: ({ signal }) => getElevenLabsOption(signal),
    retry: false,
  })
  const connections = useConnectionsServing(modelType)
  const refresh = useRefreshModels()
  const [open, setOpen] = useState(false)

  if (!option.data?.serves.includes(modelType)) return null

  const connected = connections.data?.find(
    (connection) => connection.auth_kind === "elevenlabs"
  )
  const title = intl.formatMessage({
    id: "models_elevenlabs_option_title",
    defaultMessage: "Use ElevenLabs",
  })

  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-medium">
            <AudioWaveformIcon
              aria-hidden="true"
              className="size-4 text-muted-foreground"
            />
            {title}
          </h3>
          {/* pl-6: the icon's 16px plus the 8px gap, so it lines up with the heading text. */}
          <p className="truncate pl-6 text-xs text-muted-foreground">
            {connected
              ? intl.formatMessage({
                  id: "models_elevenlabs_option_connected_body",
                  defaultMessage: "Connected with your API key",
                })
              : intl.formatMessage({
                  id: "models_elevenlabs_option_body",
                  defaultMessage:
                    "Your own account and voices, with an API key.",
                })}
          </p>
        </div>
        {connected ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => onConnected(connected)}
          >
            {intl.formatMessage({
              id: "models_elevenlabs_option_show_button",
              defaultMessage: "Show models",
            })}
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setOpen(true)}
          >
            {intl.formatMessage({
              id: "models_elevenlabs_option_connect_button",
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
                id: "models_elevenlabs_dialog_title",
                defaultMessage: "Connect ElevenLabs",
              })}
            </DialogTitle>
            <DialogDescription>{elevenLabsKeyBody()}</DialogDescription>
          </DialogHeader>
          <ElevenLabsForm
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
