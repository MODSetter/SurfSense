import { useQueryClient } from "@tanstack/react-query"
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

import { pluginsQueryKey, replacePluginKey, type Plugin } from "../api"
import { connectedToast } from "../connect-toasts"
import { refusalMessage } from "../refusal-message"

function ReplaceKeyForm({
  plugin,
  onCancel,
  onReplaced,
}: {
  plugin: Plugin
  onCancel: () => void
  onReplaced: () => void
}) {
  const fieldId = useId()
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await replacePluginKey(plugin.id, key)
      connectedToast(plugin.name)
      onReplaced()
    } catch (refused) {
      setError(
        refused instanceof ApiError && refused.code === "plugin_needs_sign_in"
          ? intl.formatMessage({
              id: "plugins_key_refused_error",
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
        <Field>
          <FieldLabel htmlFor={fieldId}>
            {intl.formatMessage({
              id: "plugins_key_connect_label",
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
            id: "plugins_key_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !key}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_key_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Connects a plugin with a key: one refused, or dropped at disconnect. It keeps its choices per tool. */
export function ReplaceKeyButton({
  plugin,
  label,
  size = "xs",
  className,
}: {
  plugin: Plugin
  label: string
  /** The button's size and extra classes, for a place whose text is larger than `xs`. */
  size?: "xs" | "sm"
  className?: string
}) {
  const queryClient = useQueryClient()
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
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="select-none sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage(
                {
                  id: "plugins_key_connect_title",
                  defaultMessage: "Connect {plugin}",
                },
                { plugin: plugin.name }
              )}
            </DialogTitle>
            <DialogDescription>
              {intl.formatMessage(
                {
                  id: "plugins_key_connect_body",
                  defaultMessage:
                    "Paste the key you use for {plugin}. Your tool settings are kept.",
                },
                { plugin: plugin.name }
              )}
            </DialogDescription>
          </DialogHeader>
          {/* The popup unmounts after closing, so each opening starts blank. */}
          <ReplaceKeyForm
            plugin={plugin}
            onCancel={() => setOpen(false)}
            onReplaced={() => {
              setOpen(false)
              void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
            }}
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
