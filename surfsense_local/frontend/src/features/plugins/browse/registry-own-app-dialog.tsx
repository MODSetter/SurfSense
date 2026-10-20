import { useQuery } from "@tanstack/react-query"
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
  connectRegistryPlugin,
  isSignInStarted,
  oauthRedirectUri,
  type RegistryEntry,
  type SignInStarted,
} from "../api"
import { refusalMessage } from "../refusal-message"
import { OwnAppFields } from "../sign-in/own-app/own-app-fields"
import {
  asOwnApp,
  EMPTY_OWN_APP,
  type OwnAppDraft,
} from "../sign-in/own-app/own-app-draft"

function RegistryOwnAppForm({
  entry,
  onCancel,
  onStarted,
}: {
  entry: RegistryEntry
  onCancel: () => void
  onStarted: (sign: SignInStarted) => void
}) {
  const [draft, setDraft] = useState<OwnAppDraft>(EMPTY_OWN_APP)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const redirectUri = useQuery({
    queryKey: ["plugins", "oauth-redirect-uri"],
    queryFn: oauthRedirectUri,
    staleTime: Infinity,
  })

  const start = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const answer = await connectRegistryPlugin(entry.id, {
        oauth_client: asOwnApp(draft),
      })
      if (isSignInStarted(answer)) onStarted(answer)
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
          disabled={busy}
        />
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_registry_own_app_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button type="submit" disabled={busy || !draft.clientId.trim()}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_registry_own_app_sign_in_button",
            defaultMessage: "Sign in",
          })}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** A registry plugin whose provider takes only apps registered in advance: the user's own. */
export function RegistryOwnAppDialog({
  entry,
  open,
  onOpenChange,
  onStarted,
}: {
  entry: RegistryEntry
  open: boolean
  onOpenChange: (open: boolean) => void
  onStarted: (sign: SignInStarted) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="select-none sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage(
              {
                id: "plugins_registry_own_app_title",
                defaultMessage: "Sign in to {plugin} with your own app",
              },
              { plugin: entry.name }
            )}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "plugins_registry_own_app_body",
              defaultMessage:
                "This plugin’s provider accepts only apps registered with it in advance. Register your own, then sign in with it.",
            })}
          </DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <RegistryOwnAppForm
          entry={entry}
          onCancel={() => onOpenChange(false)}
          onStarted={onStarted}
        />
      </DialogContent>
    </Dialog>
  )
}
