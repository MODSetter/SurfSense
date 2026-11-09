import { useQueryClient } from "@tanstack/react-query"
import { useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FieldGroup } from "@/components/ui/field"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api"

import {
  pluginsQueryKey,
  replacePluginHeaders,
  type Plugin,
  type SignInHeader,
} from "../api"
import { connectedToast } from "../connect-toasts"
import { refusalMessage } from "../refusal-message"
import {
  headersComplete,
  rowsFromNames,
  sentHeaders,
} from "./connection-headers"
import { ConnectionEditor } from "./connection-editor"
import {
  SCROLLING_DIALOG,
  SCROLLING_FIELDS,
  SCROLLING_FIELDS_VIEWPORT,
  SCROLLING_FORM,
} from "./scrolling-dialog"

function EditConnectionForm({
  plugin,
  connecting,
  onCancel,
  onSaved,
}: {
  plugin: Plugin
  connecting: boolean
  onCancel: () => void
  onSaved: () => void
}) {
  // Names come back from the API; values never do, so each is typed again.
  const [rows, setRows] = useState<SignInHeader[]>(() =>
    rowsFromNames(plugin.header_names)
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const headers = sentHeaders(rows)
  const ready = headers.length > 0 && headersComplete(rows)

  const save = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await replacePluginHeaders(plugin.id, headers)
      connectedToast(plugin.name)
      onSaved()
    } catch (refused) {
      setError(
        refused instanceof ApiError && refused.code === "plugin_needs_sign_in"
          ? intl.formatMessage({
              id: "plugins_connection_refused_error",
              defaultMessage:
                "The server refused this key. Check it and try again.",
            })
          : refusalMessage(refused)
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={SCROLLING_FORM} onSubmit={(event) => void save(event)}>
      <ScrollFade
        className={SCROLLING_FIELDS}
        viewportClassName={SCROLLING_FIELDS_VIEWPORT}
      >
        <FieldGroup>
          <ConnectionEditor rows={rows} onChange={setRows} disabled={busy} />
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </FieldGroup>
      </ScrollFade>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_connection_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !ready}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {connecting
            ? intl.formatMessage({
                id: "plugins_connection_connect_button",
                defaultMessage: "Connect",
              })
            : intl.formatMessage({
                id: "plugins_connection_save_button",
                defaultMessage: "Save",
              })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** A custom plugin's key or headers, replaced in place so it keeps its choices per tool. */
export function EditConnectionDialog({
  plugin,
  connecting = false,
  open,
  onOpenChange,
}: {
  plugin: Plugin
  /** Asks to connect a disconnected plugin rather than to save a change. */
  connecting?: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn("select-none sm:max-w-lg", SCROLLING_DIALOG)}
      >
        <DialogHeader>
          <DialogTitle>
            {connecting
              ? intl.formatMessage(
                  {
                    id: "plugins_connection_connect_title",
                    defaultMessage: "Connect {plugin}",
                  },
                  { plugin: plugin.name }
                )
              : intl.formatMessage(
                  {
                    id: "plugins_connection_title",
                    defaultMessage: "Edit the connection to {plugin}",
                  },
                  { plugin: plugin.name }
                )}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "plugins_connection_body",
              defaultMessage:
                "Enter the key again; a saved one is never shown. SurfSense tries it before saving, and your tool settings stay.",
            })}
          </DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <EditConnectionForm
          plugin={plugin}
          connecting={connecting}
          onCancel={() => onOpenChange(false)}
          onSaved={() => {
            onOpenChange(false)
            void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
          }}
        />
      </DialogContent>
    </Dialog>
  )
}

/** Connects a custom plugin again with its key or headers. */
export function EditConnectionButton({
  plugin,
  label,
  size = "xs",
  className,
}: {
  plugin: Plugin
  /** The button's text when this is how a disconnected plugin connects again. */
  label: string
  size?: "xs" | "sm"
  className?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        size={size}
        variant="secondary"
        className={className}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
      <EditConnectionDialog
        plugin={plugin}
        connecting
        open={open}
        onOpenChange={setOpen}
      />
    </>
  )
}
