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
import { useOpenPlugin } from "../open-plugin"
import { isRegistryEntry, type ListedEntry } from "../public-page/listed-entry"
import {
  connectedToast,
  connectFailedToast,
  keptToast,
} from "../connect-toasts"
import { SignInProgress } from "../sign-in/sign-in-progress"
import { usePluginSignIn } from "../sign-in/use-plugin-sign-in"
import { CommunityReminderDialog } from "./community-reminder-dialog"
import { RegistryHeadersDialog } from "./registry-headers-dialog"
import { RegistryKeyDialog } from "./registry-key-dialog"
import { SavedPluginStatus } from "./saved-plugin-status"

/**
 * Connect for any listed plugin, or its state once saved: SurfSense's with the license, a
 * registry plugin at once or with a key. One asking for an account is saved and opened in
 * Yours, where it signs in, or sets up the user's own app if its provider takes only those.
 */
export function ConnectListedPlugin({ entry }: { entry: ListedEntry }) {
  const queryClient = useQueryClient()
  const [askingKey, setAskingKey] = useState(false)
  const [askingHeaders, setAskingHeaders] = useState(false)
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
  const openPlugin = useOpenPlugin()
  // Followed here only outside Settings › Plugins, which otherwise follows it in Yours.
  const signIn = usePluginSignIn(connected)
  const connect = useMutation({
    mutationFn: () =>
      registry ? connectRegistryPlugin(entry.id) : connectFirstParty(entry.id),
    onSuccess: (answer) => {
      if (isSignInStarted(answer)) {
        if (openPlugin) openPlugin(answer.plugin_id, answer)
        else signIn.follow(answer)
      } else if (answer.needs_own_app) {
        // Kept, signed out: its details set up the app its provider needs.
        keptToast(entry.name)
        if (openPlugin) openPlugin(answer.id)
        else void refresh()
      } else connected()
    },
    onError: (error) => {
      connectFailedToast(entry.name, error)
      void refresh()
    },
  })
  const waiting = signIn.state.phase === "waiting"
  const start = () => {
    if (registry?.auth_type === "token") setAskingKey(true)
    else if (registry?.auth_type === "headers") setAskingHeaders(true)
    else connect.mutate()
  }
  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      {entry.connected ? (
        <SavedPluginStatus pluginId={entry.id} />
      ) : (
        <Button
          type="button"
          size="sm"
          variant="secondary"
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
      {registry?.auth_type === "headers" ? (
        <RegistryHeadersDialog
          entry={registry}
          open={askingHeaders}
          onOpenChange={setAskingHeaders}
          onConnected={() => {
            setAskingHeaders(false)
            connected()
          }}
        />
      ) : null}
    </div>
  )
}
