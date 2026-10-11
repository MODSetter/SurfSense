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

import { addCustomPlugin, type Plugin } from "./api"
import { refusalMessage } from "./refusal-message"

function AddPluginForm({
  onCancel,
  onAdded,
}: {
  onCancel: () => void
  onAdded: (plugin: Plugin) => void
}) {
  const fieldId = useId()
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [key, setKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connect = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onAdded(
        await addCustomPlugin({
          url: url.trim(),
          name: name.trim(),
          ...(key ? { token: key } : {}),
        })
      )
    } catch (refused) {
      setError(refusalMessage(refused))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={(event) => void connect(event)}>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor={`${fieldId}-name`}>
            {intl.formatMessage({
              id: "plugins_add_name_label",
              defaultMessage: "Name",
            })}
          </FieldLabel>
          <Input
            id={`${fieldId}-name`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={intl.formatMessage({
              id: "plugins_add_name_placeholder",
              defaultMessage: "Team wiki",
            })}
            disabled={busy}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={`${fieldId}-url`}>
            {intl.formatMessage({
              id: "plugins_add_url_label",
              defaultMessage: "Server URL",
            })}
          </FieldLabel>
          <Input
            id={`${fieldId}-url`}
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/mcp"
            disabled={busy}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={`${fieldId}-key`}>
            {intl.formatMessage({
              id: "plugins_add_key_label",
              defaultMessage: "Key",
            })}
          </FieldLabel>
          <Input
            id={`${fieldId}-key`}
            type="password"
            autoComplete="off"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder={intl.formatMessage({
              id: "plugins_add_key_placeholder",
              defaultMessage: "Optional, if the server asks for one",
            })}
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
            id: "plugins_add_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !name.trim() || !url.trim()}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_add_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Connecting a server by its URL; SurfSense lists its tools before it is added. */
export function AddPluginDialog({
  open,
  onOpenChange,
  onAdded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdded: (plugin: Plugin) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="select-none sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage({
              id: "plugins_add_title",
              defaultMessage: "Add an MCP server",
            })}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "plugins_add_body",
              defaultMessage:
                "A remote MCP server, reached by its URL. SurfSense lists its tools before adding it.",
            })}
          </DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <AddPluginForm onCancel={() => onOpenChange(false)} onAdded={onAdded} />
      </DialogContent>
    </Dialog>
  )
}
