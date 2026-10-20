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
import { ScrollFade } from "@/components/ui/scroll-fade"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import {
  isSignInStarted,
  oauthRedirectUri,
  type OwnApp,
  type Plugin,
  type SignInStarted,
} from "../../api"
import {
  SCROLLING_DIALOG,
  SCROLLING_FIELDS,
  SCROLLING_FIELDS_VIEWPORT,
  SCROLLING_FORM,
} from "../../connection/scrolling-dialog"
import { refusalMessage } from "../../refusal-message"
import { SignInProgress } from "../sign-in-progress"
import { usePluginSignIn } from "../use-plugin-sign-in"
import { OwnAppFields } from "./own-app-fields"
import { asOwnApp, EMPTY_OWN_APP, type OwnAppDraft } from "./own-app-draft"
import type { OwnAppReason } from "./own-app-reason"

function why(reason: OwnAppReason, plugin: string): string {
  if (reason === "needs_client") {
    return intl.formatMessage(
      {
        id: "plugins_own_app_needs_client_body",
        defaultMessage:
          "{plugin} accepts only apps registered with it. Register an OAuth app in its developer settings, then enter what it gives you.",
      },
      { plugin }
    )
  }
  if (reason === "refused") {
    return intl.formatMessage(
      {
        id: "plugins_own_app_refused_body",
        defaultMessage:
          "{plugin} refused to register SurfSense; it may accept only apps it approved. Register your own, then enter what it gives you.",
      },
      { plugin }
    )
  }
  return intl.formatMessage({
    id: "plugins_own_app_chosen_body",
    defaultMessage:
      "For an organization that allows only its own approved app. Your tool settings stay.",
  })
}

function OwnAppForm({
  start,
  onCancel,
  onConnected,
}: {
  start: (app: OwnApp) => Promise<Plugin | SignInStarted>
  onCancel: () => void
  onConnected: () => void
}) {
  const [draft, setDraft] = useState<OwnAppDraft>(EMPTY_OWN_APP)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const redirectUri = useQuery({
    queryKey: ["plugins", "oauth-redirect-uri"],
    queryFn: oauthRedirectUri,
    staleTime: Infinity,
  })
  const signIn = usePluginSignIn(onConnected)
  const locked = busy || signIn.state.phase === "waiting"

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const answer = await start(asOwnApp(draft))
      if (isSignInStarted(answer)) signIn.follow(answer)
      else onConnected()
    } catch (refused) {
      setError(refusalMessage(refused))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={SCROLLING_FORM} onSubmit={(event) => void submit(event)}>
      <ScrollFade
        className={SCROLLING_FIELDS}
        viewportClassName={SCROLLING_FIELDS_VIEWPORT}
      >
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
      </ScrollFade>
      <DialogFooter>
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

/**
 * Signing in as the user's own OAuth app, on its own: never among a key's fields. `start`
 * sends the app, adding a plugin or signing a saved one in again.
 */
export function OwnAppDialog({
  plugin,
  reason,
  open,
  onOpenChange,
  start,
  onConnected,
}: {
  plugin: string
  reason: OwnAppReason
  open: boolean
  onOpenChange: (open: boolean) => void
  start: (app: OwnApp) => Promise<Plugin | SignInStarted>
  onConnected: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn("select-none sm:max-w-lg", SCROLLING_DIALOG)}
      >
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage(
              {
                id: "plugins_own_app_title",
                defaultMessage: "Sign in to {plugin} with your own app",
              },
              { plugin }
            )}
          </DialogTitle>
          <DialogDescription>{why(reason, plugin)}</DialogDescription>
        </DialogHeader>
        {/* The popup unmounts after closing, so each opening starts blank. */}
        <OwnAppForm
          start={start}
          onCancel={() => onOpenChange(false)}
          onConnected={onConnected}
        />
      </DialogContent>
    </Dialog>
  )
}
