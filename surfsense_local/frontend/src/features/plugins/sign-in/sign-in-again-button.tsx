import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { pluginsQueryKey, signInAgain, type Plugin } from "../api"
import { refusalMessage } from "../refusal-message"
import { PluginOwnAppDialog } from "./own-app/plugin-own-app-dialog"
import { ownAppReason, type OwnAppReason } from "./own-app/own-app-reason"
import { useFollowSignIn, useOpenedSignIn } from "./opened-sign-in"
import { signInFailureMessage } from "./sign-in-failure-text"
import { SignInProgress } from "./sign-in-progress"

/** An OAuth plugin signed out, or disconnected, signs in again; its tool settings stay. A
 * provider taking only registered apps opens the user's own app instead of an error. */
export function SignInAgainButton({
  plugin,
  label,
  size = "xs",
  className,
}: {
  plugin: Plugin
  label: string
  /** The button's size and extra classes, for a place whose text is larger than `xs`. */
  size?: "xs" | "sm"
  className?: string
}) {
  const queryClient = useQueryClient()
  // Started when the plugin was connected elsewhere, and followed above this button.
  const opened = useOpenedSignIn(plugin.id)
  const follow = useFollowSignIn()
  const [ownApp, setOwnApp] = useState<OwnAppReason | null>(null)
  const start = useMutation({
    mutationFn: () => signInAgain(plugin.id),
    // Followed by Settings › Plugins and shown here, so leaving the row or page keeps it.
    onSuccess: (started) => follow(plugin.id, started),
    onError: (refused) => {
      setOwnApp(ownAppReason(refused))
      // Marked as needing the user's app, which its status now says.
      void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
    },
  })
  if (opened?.state.phase === "waiting") {
    return (
      <SignInProgress
        state={opened.state}
        onCancel={opened.cancel}
        className=""
      />
    )
  }
  // Why it ended, as the opened sign-in reported it.
  const failure = opened?.state.phase === "failed" ? opened.state : null
  return (
    <>
      <Button
        type="button"
        size={size}
        variant="secondary"
        className={className}
        disabled={start.isPending}
        onClick={() => {
          opened?.cancel()
          start.mutate()
        }}
      >
        {start.isPending ? <Spinner data-icon="inline-start" /> : null}
        {label}
      </Button>
      {start.error && ownAppReason(start.error) === null ? (
        <span role="alert" className="text-destructive">
          {refusalMessage(start.error)}
        </span>
      ) : null}
      {ownApp ? (
        <PluginOwnAppDialog
          plugin={plugin}
          reason={ownApp}
          open
          onOpenChange={(open) => {
            if (!open) setOwnApp(null)
          }}
        />
      ) : null}
      {failure ? (
        <span role="alert" className="text-destructive">
          {signInFailureMessage(failure) ??
            intl.formatMessage({
              id: "plugins_row_sign_in_again_error",
              defaultMessage: "The sign-in didn’t finish.",
            })}
        </span>
      ) : null}
    </>
  )
}
