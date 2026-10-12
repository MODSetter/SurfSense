import { useMutation, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { pluginsQueryKey, signInAgain, type Plugin } from "./api"
import { refusalMessage } from "./refusal-message"
import { SignInProgress } from "./sign-in-progress"
import { usePluginSignIn } from "./use-plugin-sign-in"

/** An OAuth plugin whose refresh was refused signs in again; its tool settings stay. */
export function SignInAgainButton({ plugin }: { plugin: Plugin }) {
  const queryClient = useQueryClient()
  const signIn = usePluginSignIn(
    () => void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
  )
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
        size="xs"
        variant="ghost"
        disabled={start.isPending}
        onClick={() => start.mutate()}
      >
        {start.isPending ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "plugins_row_sign_in_again_button",
          defaultMessage: "Sign in again",
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
