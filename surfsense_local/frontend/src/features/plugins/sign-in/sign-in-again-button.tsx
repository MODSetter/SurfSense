import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { pluginsQueryKey, signInAgain, type Plugin } from "../api"
import { connectedToast } from "../connect-toasts"
import { refusalMessage } from "../refusal-message"
import { PluginOwnAppDialog } from "./own-app/plugin-own-app-dialog"
import { ownAppReason, type OwnAppReason } from "./own-app/own-app-reason"
import { useOpenPlugin } from "../open-plugin"
import { useOpenedSignIn } from "./opened-sign-in"
import { SignInProgress } from "./sign-in-progress"
import { usePluginSignIn } from "./use-plugin-sign-in"

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
  const signIn = usePluginSignIn(() => {
    connectedToast(plugin.name)
    void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
  })
  // Started when the plugin was connected elsewhere, and followed above this button.
  const opened = useOpenedSignIn(plugin.id)
  const openPlugin = useOpenPlugin()
  const [ownApp, setOwnApp] = useState<OwnAppReason | null>(null)
  const start = useMutation({
    mutationFn: () => signInAgain(plugin.id),
    // Followed in the plugin's details, which a row's Connect opens, so leaving the row keeps it.
    onSuccess: (started) =>
      openPlugin ? openPlugin(plugin.id, started) : signIn.follow(started),
    onError: (refused) => {
      setOwnApp(ownAppReason(refused))
      // Marked as needing the user's app, which its status now says.
      void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
    },
  })
  const following =
    signIn.state.phase === "waiting"
      ? signIn
      : opened?.state.phase === "waiting"
        ? opened
        : null
  if (following) {
    return (
      <SignInProgress
        state={following.state}
        onCancel={following.cancel}
        className=""
      />
    )
  }
  const failed =
    signIn.state.phase === "failed" || opened?.state.phase === "failed"
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
      {failed ? (
        <span role="alert" className="text-destructive">
          {intl.formatMessage({
            id: "plugins_row_sign_in_again_error",
            defaultMessage: "The sign-in didn’t finish.",
          })}
        </span>
      ) : null}
    </>
  )
}
