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
import { ChevronDownIcon, ChevronRightIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api"

import {
  addCustomPlugin,
  isSignInStarted,
  pluginsQueryKey,
  type SignInHeader,
} from "../api"
import { connectedToast } from "../connect-toasts"
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
import { refusalMessage } from "../refusal-message"
import { OwnAppDialog } from "../sign-in/own-app/own-app-dialog"
import {
  ownAppReason,
  type OwnAppReason,
} from "../sign-in/own-app/own-app-reason"
import { SignInProgress } from "../sign-in/sign-in-progress"
import { usePluginSignIn } from "../sign-in/use-plugin-sign-in"

/**
 * Name, URL and Connect. Connect does the rest: an open server connects, one asking for
 * an account opens the browser, one asking for a key opens Advanced settings, and one
 * taking only registered apps opens the user's own app, in a dialog of its own.
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
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [rows, setRows] = useState<SignInHeader[]>(STARTING_HEADERS)
  const [advanced, setAdvanced] = useState(false)
  const [ownApp, setOwnApp] = useState<OwnAppReason | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const added = () => {
    connectedToast(name.trim())
    onAdded()
  }
  // A server asking for OAuth is kept from the start, and connected once signed in.
  const signIn = usePluginSignIn(added)
  const locked = busy || signIn.state.phase === "waiting"
  const ready = name.trim() !== "" && url.trim() !== "" && headersComplete(rows)

  const connect = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const headers = sentHeaders(rows)
    try {
      const answer = await addCustomPlugin({
        url: url.trim(),
        name: name.trim(),
        ...(headers.length ? { headers } : {}),
      })
      if (isSignInStarted(answer)) {
        signIn.follow(answer)
        // Already in Yours, waiting to sign in, should the browser be closed.
        void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
      } else {
        added()
      }
    } catch (refused) {
      const reason = ownAppReason(refused)
      if (reason !== null) {
        setOwnApp(reason)
        return
      }
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
    <>
      <form
        className={SCROLLING_FORM}
        onSubmit={(event) => void connect(event)}
      >
        <ScrollFade
          className={SCROLLING_FIELDS}
          viewportClassName={SCROLLING_FIELDS_VIEWPORT}
        >
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
                disabled={locked}
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
                disabled={locked}
              />
            </Field>
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
                disabled={locked}
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
              <ConnectionEditor
                rows={rows}
                onChange={setRows}
                disabled={locked}
              />
            ) : null}
            <SignInProgress state={signIn.state} onCancel={signIn.cancel} />
          </FieldGroup>
        </ScrollFade>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            {intl.formatMessage({
              id: "plugins_add_cancel_button",
              defaultMessage: "Cancel",
            })}
          </Button>
          <Button type="submit" disabled={locked || !ready}>
            {busy ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "plugins_add_connect_button",
              defaultMessage: "Connect",
            })}
          </Button>
        </DialogFooter>
      </form>
      {/* Beside the form, not in it: a submit inside would also submit the form. */}
      {ownApp ? (
        <OwnAppDialog
          plugin={name.trim()}
          reason={ownApp}
          open
          onOpenChange={(open) => {
            if (!open) setOwnApp(null)
          }}
          start={(app) =>
            addCustomPlugin({
              url: url.trim(),
              name: name.trim(),
              ...(sentHeaders(rows).length
                ? { headers: sentHeaders(rows) }
                : {}),
              oauth_client: app,
            })
          }
          onConnected={() => {
            setOwnApp(null)
            added()
          }}
        />
      ) : null}
    </>
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
  onAdded: () => void
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
        <AddPluginForm onCancel={() => onOpenChange(false)} onAdded={onAdded} />
      </DialogContent>
    </Dialog>
  )
}
