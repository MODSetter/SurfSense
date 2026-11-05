import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { DialogFooter } from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { updateConnection, type Connection } from "../api"
import { connectElevenLabs } from "./api"

function messageFrom(cause: unknown) {
  return cause instanceof Error
    ? cause.message
    : intl.formatMessage({
        id: "models_elevenlabs_form_save_error",
        defaultMessage: "Could not save this connection",
      })
}

/**
 * A name and a key: the address and the models are ElevenLabs' own, so nothing
 * else is the user's to set. Edits `connection` when given; a key left blank
 * keeps the saved one.
 */
export function ElevenLabsForm({
  connection,
  onCancel,
  onSaved,
}: {
  connection?: Connection
  onCancel: () => void
  onSaved: (connection: Connection) => void
}) {
  const id = useId()
  const [label, setLabel] = useState(connection?.label ?? "ElevenLabs")
  const [apiKey, setApiKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const key = apiKey.trim()
  const canSave =
    label.trim() !== "" && (connection !== undefined || key !== "")

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      onSaved(
        connection
          ? await updateConnection(connection.id, {
              label: label.trim(),
              provider: connection.provider,
              base_url: connection.base_url,
              allow_unverified: false,
              catalog_provider: connection.catalog_provider,
              ...(key ? { api_key: key } : {}),
            })
          : await connectElevenLabs({ label: label.trim(), api_key: key })
      )
    } catch (cause) {
      setError(messageFrom(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor={`${id}-name`}>
            {intl.formatMessage({
              id: "models_elevenlabs_form_name_label",
              defaultMessage: "Name",
            })}
          </FieldLabel>
          <Input
            id={`${id}-name`}
            value={label}
            maxLength={100}
            disabled={busy}
            onChange={(event) => setLabel(event.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={`${id}-key`}>
            {intl.formatMessage({
              id: "models_elevenlabs_form_key_label",
              defaultMessage: "API key",
            })}
          </FieldLabel>
          <Input
            id={`${id}-key`}
            type="password"
            autoComplete="off"
            value={apiKey}
            disabled={busy}
            placeholder={
              connection
                ? intl.formatMessage({
                    id: "models_elevenlabs_form_key_saved_placeholder",
                    defaultMessage: "Leave blank to keep the saved key",
                  })
                : undefined
            }
            onChange={(event) => setApiKey(event.target.value)}
          />
        </Field>
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "models_elevenlabs_form_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button
          type="button"
          disabled={busy || !canSave}
          onClick={() => void save()}
        >
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {connection
            ? intl.formatMessage({
                id: "models_elevenlabs_form_save_button",
                defaultMessage: "Save changes",
              })
            : intl.formatMessage({
                id: "models_elevenlabs_form_connect_button",
                defaultMessage: "Connect ElevenLabs",
              })}
        </Button>
      </DialogFooter>
    </>
  )
}
