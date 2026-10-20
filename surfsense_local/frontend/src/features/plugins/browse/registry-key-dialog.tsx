import { useId, useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import { connectRegistryPlugin, type RegistryEntry } from "../api"
import { refusalMessage } from "../refusal-message"

function RegistryKeyForm({
  entry,
  onCancel,
  onConnected,
}: {
  entry: RegistryEntry
  onCancel: () => void
  onConnected: () => void
}) {
  const fieldId = useId()
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connect = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await connectRegistryPlugin(entry.id, { token: key })
      onConnected()
    } catch (refused) {
      setError(
        refused instanceof ApiError && refused.code === "plugin_needs_sign_in"
          ? intl.formatMessage({
              id: "plugins_registry_key_refused_error",
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
    <form onSubmit={(event) => void connect(event)}>
      <FieldGroup>
        <Field>
          {/* The publisher's own name for the key, as its entry gives it. */}
          <FieldLabel htmlFor={fieldId}>
            {entry.auth_title ??
              intl.formatMessage({
                id: "plugins_registry_key_label",
                defaultMessage: "Key",
              })}
          </FieldLabel>
          <Input
            id={fieldId}
            type="password"
            autoComplete="off"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            disabled={busy}
          />
        </Field>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_registry_key_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !key}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_registry_key_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** A registry plugin that needs a key: SurfSense lists its tools with the key before saving it. */
export function RegistryKeyDialog({
  entry,
  open,
  onOpenChange,
  onConnected,
}: {
  entry: RegistryEntry
  open: boolean
  onOpenChange: (open: boolean) => void
  onConnected: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="select-none sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage(
              {
                id: "plugins_registry_key_title",
                defaultMessage: "Connect {plugin}",
              },
              { plugin: entry.name }
            )}
          </DialogTitle>
          <DialogDescription>
            {entry.auth_description ??
              intl.formatMessage({
                id: "plugins_registry_key_body",
                defaultMessage:
                  "This plugin needs a key from its publisher. SurfSense tries it before saving it.",
              })}
          </DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <RegistryKeyForm
          entry={entry}
          onCancel={() => onOpenChange(false)}
          onConnected={onConnected}
        />
      </DialogContent>
    </Dialog>
  )
}
