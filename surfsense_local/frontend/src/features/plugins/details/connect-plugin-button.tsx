import { useMutation, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { connectPlugin, pluginsQueryKey, type Plugin } from "../api"
import { refusalMessage } from "../refusal-message"
import { SignInAgainButton } from "../sign-in/sign-in-again-button"
import { ReplaceKeyButton } from "./replace-key-button"

/** Connects a disconnected plugin the way it signs in: an account, a new key, or nothing to enter. */
export function ConnectPluginButton({
  plugin,
  size = "xs",
  className,
}: {
  plugin: Plugin
  /** The button's size and extra classes, for a place whose text is larger than `xs`. */
  size?: "xs" | "sm"
  className?: string
}) {
  const queryClient = useQueryClient()
  const connect = useMutation({
    mutationFn: () => connectPlugin(plugin.id),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: pluginsQueryKey }),
  })
  const label = intl.formatMessage({
    id: "plugins_connect_button",
    defaultMessage: "Connect",
  })
  if (plugin.auth_type === "oauth") {
    return (
      <SignInAgainButton
        plugin={plugin}
        label={label}
        size={size}
        className={className}
      />
    )
  }
  if (plugin.auth_type === "token") {
    return (
      <ReplaceKeyButton
        plugin={plugin}
        label={label}
        size={size}
        className={className}
      />
    )
  }
  return (
    <>
      <Button
        type="button"
        size={size}
        variant="secondary"
        className={className}
        disabled={connect.isPending}
        onClick={() => connect.mutate()}
      >
        {connect.isPending ? <Spinner data-icon="inline-start" /> : null}
        {label}
      </Button>
      {connect.error ? (
        <span role="alert" className="text-destructive">
          {refusalMessage(connect.error)}
        </span>
      ) : null}
    </>
  )
}
