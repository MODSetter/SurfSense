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
import { connectedToast, connectFailedToast } from "../connect-toasts"
import { SignInProgress } from "../sign-in/sign-in-progress"
import { usePluginSignIn } from "../sign-in/use-plugin-sign-in"
import { CommunityReminderDialog } from "./community-reminder-dialog"
import { RegistryKeyDialog } from "./registry-key-dialog"

/**
 * Connect for any listed plugin, or "Connected": SurfSense's with the license, a
 * registry plugin at once, with a key, or by signing in in the browser.
 */
export function ConnectListedPlugin({ entry }: { entry: ListedEntry }) {
  const queryClient = useQueryClient()
  const [askingKey, setAskingKey] = useState(false)
  const [reminding, setReminding] = useState(false)
  const registry = isRegistryEntry(entry) ? entry : null
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: pluginsQueryKey }),
      queryClient.invalidateQueries({
        queryKey: registry ? registryQueryKey : firstPartyQueryKey,
      }),
    ])
  const connected = () => {
    connectedToast(entry.name)
    void refresh()
  }
  const signIn = usePluginSignIn(connected)
  const connect = useMutation({
    mutationFn: () =>
      registry ? connectRegistryPlugin(entry.id) : connectFirstParty(entry.id),
    onSuccess: (answer) => {
      // An account's sign-in finishes in the browser; the plugin exists only then.
      if (isSignInStarted(answer)) signIn.follow(answer)
      else connected()
    },
    onError: (error) => {
      connectFailedToast(entry.name, error)
      void refresh()
    },
  })
  const waiting = signIn.state.phase === "waiting"
  const start = () =>
    registry?.auth_type === "token" ? setAskingKey(true) : connect.mutate()
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
          // A community plugin's author is not proven: say so before anything is sent.
          onClick={() =>
            registry && !registry.verified ? setReminding(true) : start()
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
      {registry && !registry.verified ? (
        <CommunityReminderDialog
          plugin={entry.name}
          author={registry.author}
          open={reminding}
          onOpenChange={setReminding}
          onConnect={start}
        />
      ) : null}
      {registry?.auth_type === "token" ? (
        <RegistryKeyDialog
          entry={registry}
          open={askingKey}
          onOpenChange={setAskingKey}
          onConnected={() => {
            setAskingKey(false)
            connected()
          }}
        />
      ) : null}
    </div>
  )
}
