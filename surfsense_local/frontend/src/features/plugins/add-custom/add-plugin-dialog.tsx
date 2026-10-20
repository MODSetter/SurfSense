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
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import {
  addCustomPlugin,
  isSignInStarted,
  oauthRedirectUri,
  pluginsQueryKey,
} from "../api"
import { connectedToast } from "../connect-toasts"
import {
  connectionHeaders,
  EMPTY_CONNECTION,
  keyComplete,
  type ConnectionDraft,
} from "../connection/connection-draft"
import { ConnectionEditor } from "../connection/connection-editor"
import { refusalMessage } from "../refusal-message"
import { asOwnApp } from "../sign-in/own-app/own-app-draft"
import { SignInProgress } from "../sign-in/sign-in-progress"
import { usePluginSignIn } from "../sign-in/use-plugin-sign-in"

// Refusals Advanced settings answers: a key, or the user's own OAuth app.
const ADVANCED_REFUSALS = new Set([
  "plugin_needs_sign_in",
  "plugin_oauth_needs_client",
  "plugin_oauth_refused",
])

/**
 * Name, URL and Connect. Connect does the rest: an open server connects, one asking for
 * an account opens the browser, and only a refusal opens Advanced settings, at the field
 * that answers it.
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
  const [draft, setDraft] = useState<ConnectionDraft>(EMPTY_CONNECTION)
  const [advanced, setAdvanced] = useState(false)
  const [redirectUri, setRedirectUri] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const added = () => {
    connectedToast(name.trim())
    onAdded()
  }
  // A server asking for OAuth is kept from the start, and connected once signed in.
  const signIn = usePluginSignIn(added)
  const locked = busy || signIn.state.phase === "waiting"
  const ready =
    name.trim() !== "" &&
    url.trim() !== "" &&
    (!draft.key || keyComplete(draft))

  const openAdvanced = () => {
    setAdvanced(true)
    if (redirectUri === null) {
      oauthRedirectUri()
        .then(setRedirectUri)
        .catch(() => {
          // The field stays empty; Connect still says what is missing.
        })
    }
  }

  const connect = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const headers = connectionHeaders(draft)
    try {
      const answer = await addCustomPlugin({
        url: url.trim(),
        name: name.trim(),
        ...(headers.length ? { headers } : {}),
        ...(draft.ownApp.clientId.trim()
          ? { oauth_client: asOwnApp(draft.ownApp) }
          : {}),
      })
      if (isSignInStarted(answer)) {
        signIn.follow(answer)
        // Already in Yours, waiting to sign in, should the browser be closed.
        void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
      } else {
        added()
      }
    } catch (refused) {
      setError(refusalMessage(refused))
      if (
        refused instanceof ApiError &&
        ADVANCED_REFUSALS.has(refused.code ?? "")
      ) {
        const redirect = refused.detail.redirect_uri
        if (typeof redirect === "string") setRedirectUri(redirect)
        openAdvanced()
      }
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
            onClick={() => (advanced ? setAdvanced(false) : openAdvanced())}
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
            draft={draft}
            onChange={setDraft}
            withOAuth
            redirectUri={redirectUri}
            disabled={locked}
          />
        ) : null}
        <SignInProgress state={signIn.state} onCancel={signIn.cancel} />
      </FieldGroup>
      <DialogFooter className="mt-6">
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
      <DialogContent className="select-none sm:max-w-lg">
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
