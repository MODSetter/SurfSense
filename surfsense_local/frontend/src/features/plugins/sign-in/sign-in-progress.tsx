import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { signInFailureMessage } from "./sign-in-failure-text"
import type { PluginSignInState } from "./use-plugin-sign-in"

/** "Waiting for sign-in…" with Cancel while the browser is open, or why it did not finish. */
export function SignInProgress({
  state,
  onCancel,
  className = "mt-1",
}: {
  state: PluginSignInState
  onCancel: () => void
  className?: string
}) {
  if (state.phase === "waiting") {
    return (
      <div
        className={cn(
          "flex items-center gap-2 text-xs text-muted-foreground",
          className
        )}
      >
        <span className="flex items-center gap-1.5">
          <Spinner />
          {intl.formatMessage({
            id: "plugins_sign_in_waiting_status",
            defaultMessage: "Waiting for sign-in…",
          })}
        </span>
        <Button type="button" size="xs" variant="ghost" onClick={onCancel}>
          {intl.formatMessage({
            id: "plugins_sign_in_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
      </div>
    )
  }
  if (state.phase === "failed") {
    return (
      <p role="alert" className={cn("text-xs text-destructive", className)}>
        {signInFailureMessage(state) ??
          intl.formatMessage({
            id: "plugins_sign_in_failed_error",
            defaultMessage: "The sign-in didn’t finish. Try again.",
          })}
      </p>
    )
  }
  return null
}
