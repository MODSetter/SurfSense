import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import {
  connectFirstParty,
  connectRegistryPlugin,
  firstPartyQueryKey,
  isSignInStarted,
  pluginsQueryKey,
  registryQueryKey,
} from "../api"
import { isRegistryEntry, type ListedEntry } from "../public-page/listed-entry"
import { refusalMessage } from "../refusal-message"
import { SignInProgress } from "../sign-in/sign-in-progress"
import { usePluginSignIn } from "../sign-in/use-plugin-sign-in"
import { RegistryKeyDialog } from "./registry-key-dialog"

/**
 * Connect for any listed plugin, or "Connected": SurfSense's with the license, a
 * registry plugin at once, with a key, or by signing in in the browser.
 */
export function ConnectListedPlugin({ entry }: { entry: ListedEntry }) {
  const queryClient = useQueryClient()
  const [askingKey, setAskingKey] = useState(false)
  const registry = isRegistryEntry(entry) ? entry : null
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: pluginsQueryKey }),
      queryClient.invalidateQueries({
        queryKey: registry ? registryQueryKey : firstPartyQueryKey,
      }),
    ])
  const signIn = usePluginSignIn(() => void refresh())
  const connect = useMutation({
    mutationFn: () =>
      registry ? connectRegistryPlugin(entry.id) : connectFirstParty(entry.id),
    onSuccess: (answer) => {
      // An account's sign-in finishes in the browser; the plugin exists only then.
      if (isSignInStarted(answer)) signIn.follow(answer)
      else void refresh()
    },
    onError: () => void refresh(),
  })
  const waiting = signIn.state.phase === "waiting"
  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      {entry.connected ? (
        <span className="text-xs text-muted-foreground">
          {intl.formatMessage({
            id: "plugins_listed_connected_status",
            defaultMessage: "Connected",
          })}
        </span>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={waiting || connect.isPending}
          onClick={() =>
            registry?.auth_type === "token"
              ? setAskingKey(true)
              : connect.mutate()
          }
        >
          {connect.isPending ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "plugins_listed_connect_button",
            defaultMessage: "Connect",
          })}
        </Button>
      )}
      <SignInProgress state={signIn.state} onCancel={signIn.cancel} />
      {connect.error ? (
        <p
          role="alert"
          className="max-w-56 text-right text-xs text-destructive"
        >
          {refusalMessage(connect.error)}
        </p>
      ) : null}
      {registry?.auth_type === "token" ? (
        <RegistryKeyDialog
          entry={registry}
          open={askingKey}
          onOpenChange={setAskingKey}
          onConnected={() => {
            setAskingKey(false)
            void refresh()
          }}
        />
      ) : null}
    </div>
  )
}
