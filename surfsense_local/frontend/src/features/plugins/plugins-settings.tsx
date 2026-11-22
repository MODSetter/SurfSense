import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import {
  firstPartyQueryKey,
  listPlugins,
  pluginsQueryKey,
  registryQueryKey,
  type Plugin,
  type SignInStarted,
} from "./api"
import { AddPluginDialog } from "./add-custom/add-plugin-dialog"
import { BrowsePlugins } from "./browse/browse-plugins"
import { connectedToast } from "./connect-toasts"
import { OpenPluginContext } from "./open-plugin"
import { OpenedSignInContext } from "./sign-in/opened-sign-in"
import { usePluginSignIn } from "./sign-in/use-plugin-sign-in"
import { PluginSearchField } from "./search/plugin-search-field"
import { PluginSearchResults } from "./search/plugin-search-results"
import { refreshLicenseVerdict } from "./license-verdict"
import { YourPlugins } from "./yours/your-plugins"

type Tab = "yours" | "browse"

/** Where Plugins opens from elsewhere: Browse, or the Add custom plugin dialog. */
export type PluginsStart = "browse" | "add"

export function PluginsSettings({
  start,
  onOpenLicense,
}: {
  start?: PluginsStart
  /** Shown on a plugin whose license was refused. */
  onOpenLicense?: () => void
}) {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(start === "add")
  // A license changed or expired since the last answer shows here, not at the next turn.
  useEffect(() => {
    void refreshLicenseVerdict(queryClient, { ifStale: true })
  }, [queryClient])
  const [query, setQuery] = useState("")
  // Whose details show in Yours: here, so a plugin just kept to finish can open.
  const [openId, setOpenId] = useState<string | null>(null)
  // While searching, results from both tabs replace them, so the tabs wait.
  const searching = query.trim() !== ""
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
  })
  // Chosen once the list first answers, so connecting from Browse keeps the user there.
  const [tab, setTab] = useState<Tab | null>(
    start === "browse" ? "browse" : null
  )
  // Followed here, so a sign-in outlives the row, page or dialog that started it.
  const [signingIn, setSigningIn] = useState<string | null>(null)
  const refresh = () =>
    Promise.all(
      [pluginsQueryKey, registryQueryKey, firstPartyQueryKey].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey })
      )
    )
  const signIn = usePluginSignIn(() => {
    const name = queryClient
      .getQueryData<Plugin[]>(pluginsQueryKey)
      ?.find((plugin) => plugin.id === signingIn)?.name
    if (name) connectedToast(name)
    void refresh()
  })
  const followSignIn = (pluginId: string, started: SignInStarted) => {
    setSigningIn(pluginId)
    signIn.follow(started)
  }
  // Browse, its pages and search finish a plugin in its details in Yours.
  const openPlugin = async (pluginId: string, started?: SignInStarted) => {
    setAdding(false)
    setQuery("")
    setTab("yours")
    // The browser opens at once; the details follow once the list has the plugin.
    if (started) followSignIn(pluginId, started)
    await refresh()
    setOpenId(pluginId)
  }
  if (tab === null && plugins.data) {
    setTab(plugins.data.length ? "yours" : "browse")
  } else if (tab === null && plugins.error) {
    setTab("yours")
  }

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "plugins_settings_title",
        defaultMessage: "Plugins",
      })}
      description={intl.formatMessage({
        id: "plugins_settings_body",
        defaultMessage:
          "Tools from MCP servers that the agent can use. Plugins work in Agentic threads.",
      })}
    >
      <OpenPluginContext.Provider
        value={(id, started) => void openPlugin(id, started)}
      >
        <OpenedSignInContext.Provider
          value={{
            pluginId: signingIn,
            state: signIn.state,
            cancel: signIn.cancel,
            follow: followSignIn,
          }}
        >
          <Tabs
            value={tab ?? "yours"}
            onValueChange={(value: Tab) => {
              setTab(value)
              // Coming back to Yours shows the list, as it did when Yours held this itself.
              setOpenId(null)
            }}
            className="gap-5"
          >
            <div className="flex items-center justify-between gap-4">
              <TabsList variant="pill" activateOnFocus>
                <TabsTrigger value="yours" disabled={searching}>
                  {intl.formatMessage({
                    id: "plugins_settings_yours_label",
                    defaultMessage: "Yours",
                  })}
                </TabsTrigger>
                <TabsTrigger value="browse" disabled={searching}>
                  {intl.formatMessage({
                    id: "plugins_settings_browse_label",
                    defaultMessage: "Browse",
                  })}
                </TabsTrigger>
              </TabsList>
              <div className="flex min-w-0 items-center gap-2">
                <PluginSearchField value={query} onChange={setQuery} />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8 shrink-0"
                  onClick={() => setAdding(true)}
                >
                  <PlusIcon data-icon="inline-start" />
                  {intl.formatMessage({
                    id: "plugins_settings_add_custom_button",
                    defaultMessage: "Add custom plugin",
                  })}
                </Button>
              </div>
            </div>
            {searching ? (
              <PluginSearchResults
                query={query}
                plugins={plugins}
                onOpenLicense={onOpenLicense}
              />
            ) : (
              <>
                <TabsContent value="yours">
                  <YourPlugins
                    plugins={plugins}
                    openId={openId}
                    onOpenIdChange={setOpenId}
                    onBrowse={() => setTab("browse")}
                    onAdd={() => setAdding(true)}
                    onOpenLicense={onOpenLicense}
                  />
                </TabsContent>
                <TabsContent value="browse">
                  <BrowsePlugins />
                </TabsContent>
              </>
            )}
          </Tabs>
          <AddPluginDialog
            open={adding}
            onOpenChange={setAdding}
            onAdded={() => setTab("yours")}
          />
        </OpenedSignInContext.Provider>
      </OpenPluginContext.Provider>
    </SettingsSection>
  )
}
