import { useQueryClient } from "@tanstack/react-query"
import { useId, useState, type FormEvent } from "react"

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

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await replacePluginKey(plugin.id, key)
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
              id: "plugins_key_new_label",
              defaultMessage: "New key",
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
            id: "plugins_key_save_button",
            defaultMessage: "Save",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** A refused key replaced in place, so the plugin keeps its choices per tool. */
export function ReplaceKeyButton({ plugin }: { plugin: Plugin }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        size="xs"
        variant="ghost"
        onClick={() => setOpen(true)}
      >
        {intl.formatMessage({
          id: "plugins_key_replace_button",
          defaultMessage: "Replace key",
        })}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="select-none sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage(
                {
                  id: "plugins_key_title",
                  defaultMessage: "Replace the key for {plugin}",
                },
                { plugin: plugin.name }
              )}
            </DialogTitle>
            <DialogDescription>
              {intl.formatMessage({
                id: "plugins_key_body",
                defaultMessage:
                  "SurfSense tries the new key before saving it. Your tool settings stay.",
              })}
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
