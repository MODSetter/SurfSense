import { useQuery, useQueryClient } from "@tanstack/react-query"
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

import {
  oauthRedirectUri,
  pluginsQueryKey,
  signInAgain,
  type Plugin,
} from "../../api"
import { connectedToast } from "../../connect-toasts"
import { refusalMessage } from "../../refusal-message"
import { SignInProgress } from "../sign-in-progress"
import { usePluginSignIn } from "../use-plugin-sign-in"
import { OwnAppFields } from "./own-app-fields"
import { asOwnApp, EMPTY_OWN_APP, type OwnAppDraft } from "./own-app-draft"

function OwnAppForm({
  plugin,
  onCancel,
  onSignedIn,
}: {
  plugin: Plugin
  onCancel: () => void
  onSignedIn: () => void
}) {
  const [draft, setDraft] = useState<OwnAppDraft>(EMPTY_OWN_APP)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const redirectUri = useQuery({
    queryKey: ["plugins", "oauth-redirect-uri"],
    queryFn: oauthRedirectUri,
    staleTime: Infinity,
  })
  const signIn = usePluginSignIn(onSignedIn)
  const locked = busy || signIn.state.phase === "waiting"

  const start = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      signIn.follow(await signInAgain(plugin.id, asOwnApp(draft)))
    } catch (refused) {
      setError(refusalMessage(refused))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={(event) => void start(event)}>
      <FieldGroup>
        <OwnAppFields
          value={draft}
          onChange={setDraft}
          redirectUri={redirectUri.data ?? null}
          disabled={locked}
        />
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <SignInProgress state={signIn.state} onCancel={signIn.cancel} />
      </FieldGroup>
      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_own_app_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={locked || !draft.clientId.trim()}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_own_app_sign_in_button",
            defaultMessage: "Sign in",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Signs an OAuth plugin in as the user's own app, for a provider taking only registered ones. */
export function OwnAppSignInButton({ plugin }: { plugin: Plugin }) {
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
          id: "plugins_own_app_button",
          defaultMessage: "Use your own OAuth app",
        })}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="select-none sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage(
                {
                  id: "plugins_own_app_title",
                  defaultMessage: "Sign in to {plugin} with your own app",
                },
                { plugin: plugin.name }
              )}
            </DialogTitle>
            <DialogDescription>
              {intl.formatMessage({
                id: "plugins_own_app_body",
                defaultMessage:
                  "For a provider that accepts only apps registered with it. Your tool settings stay.",
              })}
            </DialogDescription>
          </DialogHeader>
          {/* The popup unmounts after closing, so each opening starts blank. */}
          <OwnAppForm
            plugin={plugin}
            onCancel={() => setOpen(false)}
            onSignedIn={() => {
              setOpen(false)
              connectedToast(plugin.name)
              void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
            }}
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
