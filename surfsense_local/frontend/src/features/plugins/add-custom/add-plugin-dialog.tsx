import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useId, useState, type SubmitEvent } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
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
import {
  ChevronDownIcon,
  ChevronRightIcon,
  CircleAlertIcon,
} from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api"

import {
  addCustomPlugin,
  pluginsQueryKey,
  thirdPartyAllowed,
  thirdPartyQueryKey,
  type SignInHeader,
} from "../api"
import { addedToast } from "../connect-toasts"
import {
  headersComplete,
  sentHeaders,
  STARTING_HEADERS,
} from "../connection/connection-headers"
import { ConnectionEditor } from "../connection/connection-editor"
import {
  SCROLLING_DIALOG,
  SCROLLING_FIELDS,
  SCROLLING_FIELDS_VIEWPORT,
  SCROLLING_FORM,
} from "../connection/scrolling-dialog"
import { ThirdPartySwitch } from "../browse/third-party-switch"
import { usePluginChanges } from "../details/use-plugin-changes"
import { refusalMessage } from "../refusal-message"
import { isSseAddress } from "./sse-address"

/**
 * Name, URL and Add. Add puts the server in Yours: an open server or one with its key works at
 * once, one asking for a key it was not given opens Advanced settings, and one asking for an
 * account waits for Connect on its row, as Claude's custom connectors do.
 */
function AddPluginForm({
  onCancel,
  onAdded,
}: {
  onCancel: () => void
  onAdded: () => void
}) {
  const fieldId = useId()
  const queryClient = useQueryClient()
  // A server added by URL is a third-party plugin: adding one reaches it, so it waits for
  // the switch, allowed here with the same consent as in Browse.
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  const changes = usePluginChanges()
  const allowed = thirdParty.data ?? false
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [rows, setRows] = useState<SignInHeader[]>(STARTING_HEADERS)
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sse = isSseAddress(url)
  const ready =
    name.trim() !== "" && url.trim() !== "" && !sse && headersComplete(rows)

  const add = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const headers = sentHeaders(rows)
    try {
      const plugin = await addCustomPlugin({
        url: url.trim(),
        name: name.trim(),
        ...(headers.length ? { headers } : {}),
      })
      addedToast(plugin)
      void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
      onAdded()
    } catch (refused) {
      setError(refusalMessage(refused))
      if (
        refused instanceof ApiError &&
        refused.code === "plugin_needs_sign_in"
      ) {
        setAdvanced(true)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={SCROLLING_FORM} onSubmit={(event) => void add(event)}>
      <ScrollFade
        className={SCROLLING_FIELDS}
        viewportClassName={SCROLLING_FIELDS_VIEWPORT}
      >
        <FieldGroup>
          {thirdParty.data === false ? (
            <div className="flex items-center justify-between gap-4 rounded-lg bg-muted/50 p-3">
              <p className="text-sm text-pretty text-muted-foreground">
                {intl.formatMessage({
                  id: "plugins_add_third_party_body",
                  defaultMessage:
                    "A server added by URL is a third-party plugin. Allow them to add one.",
                })}
              </p>
              <ThirdPartySwitch
                allowed={false}
                onChange={(next) => changes.thirdParty.mutate(next)}
              />
            </div>
          ) : null}
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
          {sse ? (
            <Alert variant="destructive">
              <CircleAlertIcon />
              <AlertDescription>
                {intl.formatMessage({
                  id: "plugins_add_sse_body",
                  defaultMessage:
                    "SurfSense doesn’t support SSE servers. Use the server’s Streamable HTTP address, which often ends in /mcp.",
                })}
              </AlertDescription>
            </Alert>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
          <div className="flex">
            <Button
              type="button"
              size="xs"
              variant="ghost"
              className="-ml-2"
              aria-expanded={advanced}
              disabled={busy}
              onClick={() => setAdvanced(!advanced)}
            >
              {advanced ? (
                <ChevronDownIcon data-icon="inline-start" />
              ) : (
                <ChevronRightIcon data-icon="inline-start" />
              )}
              {intl.formatMessage({
                id: "plugins_add_advanced_button",
                defaultMessage: "Advanced settings",
              })}
            </Button>
          </div>
          {advanced ? (
            <ConnectionEditor rows={rows} onChange={setRows} disabled={busy} />
          ) : null}
        </FieldGroup>
      </ScrollFade>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_add_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !ready || !allowed}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_add_submit_button",
            defaultMessage: "Add",
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
  /** Connected at once; one still to finish is opened in Yours instead. */
  onAdded?: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn("select-none sm:max-w-lg", SCROLLING_DIALOG)}
      >
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
        <AddPluginForm
          onCancel={() => onOpenChange(false)}
          onAdded={() => {
            onOpenChange(false)
            onAdded?.()
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
