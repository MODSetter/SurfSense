import { useQueryClient } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"

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
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import { pluginsQueryKey, replacePluginHeaders, type Plugin } from "../api"
import { connectedToast } from "../connect-toasts"
import { refusalMessage } from "../refusal-message"
import {
  connectionHeaders,
  draftFromNames,
  keyComplete,
  type ConnectionDraft,
} from "./connection-draft"
import { ConnectionEditor } from "./connection-editor"

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
  const [draft, setDraft] = useState<ConnectionDraft>(() =>
    draftFromNames(plugin.header_names)
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const headers = connectionHeaders(draft)
  const ready = headers.length > 0 && keyComplete(draft)

  const save = async (event: FormEvent) => {
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
    <form onSubmit={(event) => void save(event)}>
      <FieldGroup>
        <ConnectionEditor
          draft={draft}
          onChange={setDraft}
          withOAuth={false}
          redirectUri={null}
          disabled={busy}
        />
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter className="mt-6">
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
export function EditConnectionButton({
  plugin,
  label,
  size = "xs",
  className,
}: {
  plugin: Plugin
  /** The button's text when this is how a disconnected plugin connects again. */
  label?: string
  size?: "xs" | "sm"
  className?: string
}) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const connecting = label !== undefined
  return (
    <>
      <Button
        type="button"
        size={size}
        variant={connecting ? "secondary" : "ghost"}
        className={className}
        onClick={() => setOpen(true)}
      >
        {label ??
          intl.formatMessage({
            id: "plugins_connection_edit_button",
            defaultMessage: "Edit connection",
          })}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="select-none sm:max-w-lg">
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
            onCancel={() => setOpen(false)}
            onSaved={() => {
              setOpen(false)
              void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
            }}
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
