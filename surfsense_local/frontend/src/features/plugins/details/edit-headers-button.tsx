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
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import {
  pluginsQueryKey,
  replacePluginHeaders,
  type Plugin,
  type SignInHeader,
} from "../api"
import { connectedToast } from "../connect-toasts"
import { filledHeaders } from "../headers/filled-headers"
import { HeaderRows } from "../headers/header-rows"
import { refusalMessage } from "../refusal-message"

function EditHeadersForm({
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
  const [rows, setRows] = useState<SignInHeader[]>(
    plugin.header_names.length
      ? plugin.header_names.map((name) => ({ name, value: "" }))
      : [{ name: "", value: "" }]
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const filled = filledHeaders(rows)
  const complete =
    filled.length > 0 && filled.every((row) => row.name && row.value)

  const save = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await replacePluginHeaders(plugin.id, filled)
      connectedToast(plugin.name)
      onSaved()
    } catch (refused) {
      setError(
        refused instanceof ApiError && refused.code === "plugin_needs_sign_in"
          ? intl.formatMessage({
              id: "plugins_headers_refused_error",
              defaultMessage:
                "The server refused these headers. Check them and try again.",
            })
          : refusalMessage(refused)
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={(event) => void save(event)}>
      <HeaderRows rows={rows} onChange={setRows} disabled={busy} />
      {error ? (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_headers_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !complete}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {connecting
            ? intl.formatMessage({
                id: "plugins_headers_connect_button",
                defaultMessage: "Connect",
              })
            : intl.formatMessage({
                id: "plugins_headers_save_button",
                defaultMessage: "Save",
              })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** A plugin's headers replaced in place, refused or dropped at disconnect, so it keeps its choices per tool. */
export function EditHeadersDialog({
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
      <DialogContent className="select-none sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {connecting
              ? intl.formatMessage(
                  {
                    id: "plugins_headers_connect_title",
                    defaultMessage: "Connect {plugin}",
                  },
                  { plugin: plugin.name }
                )
              : intl.formatMessage(
                  {
                    id: "plugins_headers_title",
                    defaultMessage: "Edit the headers for {plugin}",
                  },
                  { plugin: plugin.name }
                )}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "plugins_headers_body",
              defaultMessage:
                "Enter each value again; saved values are never shown. SurfSense tries them before saving, and your tool settings stay.",
            })}
          </DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <EditHeadersForm
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

/** Connects a registry plugin again with the headers its entry names. */
export function EditHeadersButton({
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
      <EditHeadersDialog
        plugin={plugin}
        connecting
        open={open}
        onOpenChange={setOpen}
      />
    </>
  )
}
