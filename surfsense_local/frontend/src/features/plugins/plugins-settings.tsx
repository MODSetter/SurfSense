import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { PlusIcon } from "@/components/ui/icons"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { listPlugins, pluginsQueryKey } from "./api"
import { AddPluginDialog } from "./add-custom/add-plugin-dialog"
import { BrowsePlugins } from "./browse/browse-plugins"
import { YourPlugins } from "./yours/your-plugins"

type Tab = "yours" | "browse"

export function PluginsSettings({
  onOpenLicense,
}: {
  /** Shown on a plugin whose license was refused. */
  onOpenLicense?: () => void
}) {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const plugins = useQuery({
    queryKey: pluginsQueryKey,
    queryFn: ({ signal }) => listPlugins(signal),
  })
  // Chosen once the list first answers, so connecting from Browse keeps the user there.
  const [tab, setTab] = useState<Tab | null>(null)
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
      <Tabs
        value={tab ?? "yours"}
        onValueChange={(value: Tab) => setTab(value)}
        className="gap-5"
      >
        <div className="flex items-center justify-between gap-4">
          <TabsList activateOnFocus>
            <TabsTrigger value="yours" className="px-3">
              {intl.formatMessage({
                id: "plugins_settings_yours_label",
                defaultMessage: "Yours",
              })}
            </TabsTrigger>
            <TabsTrigger value="browse" className="px-3">
              {intl.formatMessage({
                id: "plugins_settings_browse_label",
                defaultMessage: "Browse",
              })}
            </TabsTrigger>
          </TabsList>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setAdding(true)}
          >
            <PlusIcon data-icon="inline-start" />
            {intl.formatMessage({
              id: "plugins_settings_add_custom_button",
              defaultMessage: "Add custom plugin",
            })}
          </Button>
        </div>
        <TabsContent value="yours">
          <YourPlugins
            plugins={plugins}
            onBrowse={() => setTab("browse")}
            onAdd={() => setAdding(true)}
            onOpenLicense={onOpenLicense}
          />
        </TabsContent>
        <TabsContent value="browse">
          <BrowsePlugins />
        </TabsContent>
      </Tabs>
      <AddPluginDialog
        open={adding}
        onOpenChange={setAdding}
        onAdded={() => {
          setAdding(false)
          setTab("yours")
          void queryClient.invalidateQueries({ queryKey: pluginsQueryKey })
        }}
      />
    </SettingsSection>
  )
}
