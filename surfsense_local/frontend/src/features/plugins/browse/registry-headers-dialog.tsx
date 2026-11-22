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
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import { connectRegistryPlugin, type RegistryEntry } from "../api"
import { refusalMessage } from "../refusal-message"

function RegistryHeadersForm({
  entry,
  onCancel,
  onConnected,
}: {
  entry: RegistryEntry
  onCancel: () => void
  onConnected: () => void
}) {
  const fieldId = useId()
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const complete = entry.auth_headers.every((h) => values[h.name])

  const connect = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await connectRegistryPlugin(entry.id, {
        headers: entry.auth_headers.map((h) => ({
          name: h.name,
          value: values[h.name],
        })),
      })
      onConnected()
    } catch (refused) {
      setError(
        refused instanceof ApiError && refused.code === "plugin_needs_sign_in"
          ? intl.formatMessage({
              id: "plugins_registry_headers_refused_error",
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
        {entry.auth_headers.map((header, index) => (
          <Field key={header.name}>
            {/* The entry's own words; the header's name when it gives none. */}
            <FieldLabel htmlFor={`${fieldId}-${index}`}>
              {header.label ?? header.name}
            </FieldLabel>
            <Input
              id={`${fieldId}-${index}`}
              type="password"
              autoComplete="off"
              value={values[header.name] ?? ""}
              onChange={(event) =>
                setValues({ ...values, [header.name]: event.target.value })
              }
              disabled={busy}
            />
            {header.description ? (
              <FieldDescription>{header.description}</FieldDescription>
            ) : null}
          </Field>
        ))}
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_registry_headers_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !complete}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_registry_headers_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** A registry plugin whose key goes in headers its entry names: a value for each. */
export function RegistryHeadersDialog({
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
                id: "plugins_registry_headers_title",
                defaultMessage: "Connect {plugin}",
              },
              { plugin: entry.name }
            )}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "plugins_registry_headers_body",
              defaultMessage:
                "This plugin needs a key from its publisher. SurfSense tries it before saving it.",
            })}
          </DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <RegistryHeadersForm
          entry={entry}
          onCancel={() => onOpenChange(false)}
          onConnected={onConnected}
        />
      </DialogContent>
    </Dialog>
  )
}
