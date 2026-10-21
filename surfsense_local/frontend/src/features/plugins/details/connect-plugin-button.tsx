import { useMutation, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { connectPlugin, pluginsQueryKey, type Plugin } from "../api"
import { connectedToast, connectFailedToast } from "../connect-toasts"
import { OwnAppButton } from "../sign-in/own-app/own-app-button"
import { SignInAgainButton } from "../sign-in/sign-in-again-button"
import { EditConnectionButton } from "../connection/edit-connection-button"
import { EditHeadersButton } from "./edit-headers-button"
import { ReplaceKeyButton } from "./replace-key-button"

/** Connects a plugin not connected the way it signs in: an account, the user's own OAuth app
 * where its provider takes no other, a new key or headers, or nothing to enter. */
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
    onSuccess: () => connectedToast(plugin.name),
    onError: (error) => connectFailedToast(plugin.name, error),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: pluginsQueryKey }),
  })
  const label = intl.formatMessage({
    id: "plugins_connect_button",
    defaultMessage: "Connect",
  })
  if (plugin.auth_type === "oauth" && plugin.needs_own_app) {
    return (
      <OwnAppButton
        plugin={plugin}
        reason={plugin.needs_own_app}
        label={label}
        size={size}
        className={className}
      />
    )
  }
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
  if (plugin.auth_type === "headers" && plugin.source === "custom") {
    return (
      <EditConnectionButton
        plugin={plugin}
        label={label}
        size={size}
        className={className}
      />
    )
  }
  if (plugin.auth_type === "headers") {
    return (
      <EditHeadersButton
        plugin={plugin}
        label={label}
        size={size}
        className={className}
      />
    )
  }
  // An open server that now refuses without a key takes one the same way.
  if (plugin.auth_type === "token" || plugin.check_failure === "sign_in") {
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
    </>
  )
}
