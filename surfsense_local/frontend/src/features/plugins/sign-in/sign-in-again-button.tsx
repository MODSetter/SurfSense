import { useMutation, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { pluginsQueryKey, signInAgain, type Plugin } from "../api"
import { connectedToast } from "../connect-toasts"
import { refusalMessage } from "../refusal-message"
import { SignInProgress } from "./sign-in-progress"
import { usePluginSignIn } from "./use-plugin-sign-in"

/** An OAuth plugin signed out, or disconnected, signs in again; its tool settings stay. */
export function SignInAgainButton({
  plugin,
  label,
  size = "xs",
  className,
}: {
  plugin: Plugin
  /** The button's text when signing in is how the plugin connects again. Shown as a secondary button. */
  label?: string
  /** The button's size and extra classes, for a place whose text is larger than `xs`. */
  size?: "xs" | "sm"
  className?: string
}) {
  const queryClient = useQueryClient()
  const signIn = usePluginSignIn(() => {
    connectedToast(plugin.name)
    void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
  })
  const start = useMutation({
    mutationFn: () => signInAgain(plugin.id),
    onSuccess: signIn.follow,
  })
  if (signIn.state.phase === "waiting") {
    return (
      <SignInProgress
        state={signIn.state}
        onCancel={signIn.cancel}
        className=""
      />
    )
  }
  return (
    <>
      <Button
        type="button"
        size={size}
        variant={label ? "secondary" : "ghost"}
        className={className}
        disabled={start.isPending}
        onClick={() => start.mutate()}
      >
        {start.isPending ? <Spinner data-icon="inline-start" /> : null}
        {label ??
          intl.formatMessage({
            id: "plugins_row_sign_in_button",
            defaultMessage: "Sign in",
          })}
      </Button>
      {start.error ? (
        <span role="alert" className="text-destructive">
          {refusalMessage(start.error)}
        </span>
      ) : null}
      {signIn.state.phase === "failed" ? (
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
