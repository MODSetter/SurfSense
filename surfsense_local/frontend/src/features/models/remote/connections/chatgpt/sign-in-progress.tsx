import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { needsPastedCallback } from "./needs-pasted-callback"
import { PasteCallback } from "./paste-callback"
import { openSignInPage, type SignInState } from "./use-sign-in"

/** Where a ChatGPT sign-in stands, in the dialog and beside Use a server alike. */
export function SignInProgress({ state }: { state: SignInState }) {
  if (state.phase === "waiting")
    return (
      <div className="flex flex-col gap-2 text-sm" role="status">
        <p className="flex items-center gap-2 text-muted-foreground">
          <Spinner />
          {intl.formatMessage({
            id: "models_chatgpt_waiting_status",
            defaultMessage: "Finish signing in in your browser.",
          })}
        </p>
        <Button
          type="button"
          variant="link"
          className="self-start px-0"
          onClick={() => openSignInPage(state.authorizeUrl)}
        >
          {intl.formatMessage({
            id: "models_chatgpt_reopen_button",
            defaultMessage: "Open the sign-in page again",
          })}
        </Button>
        {needsPastedCallback() ? <PasteCallback flowId={state.flowId} /> : null}
      </div>
    )
  if (state.phase === "declined")
    return (
      <p className="text-sm text-destructive" role="alert">
        {intl.formatMessage(
          {
            id: "models_chatgpt_host_declined_error",
            defaultMessage:
              "Signing in needs {host}. Allow it in Settings › Network to continue.",
          },
          { host: state.host }
        )}
      </p>
    )
  if (state.phase === "failed")
    return (
      <div className="flex flex-col gap-1 text-sm" role="alert">
        <p className="text-destructive">
          {intl.formatMessage({
            id: "models_chatgpt_sign_in_error",
            defaultMessage: "The sign-in didn’t finish.",
          })}
        </p>
        {state.detail ? (
          <p className="text-muted-foreground">{state.detail}</p>
        ) : null}
      </div>
    )
  return null
}
