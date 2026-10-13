import { useQuery } from "@tanstack/react-query"
import { useId } from "react"

import { intl } from "@/i18n/intl"

import {
  thirdPartyAllowed,
  thirdPartyQueryKey,
  type RegistryEntry,
} from "../api"
import { RegistryPlugins } from "./registry-plugins"
import { ThirdPartySwitch } from "./third-party-switch"
import { usePluginChanges } from "../details/use-plugin-changes"

/** The registry's plugins, behind the switch that allows third-party plugins at all. */
export function ThirdPartyPlugins({
  onOpen,
}: {
  onOpen: (entry: RegistryEntry) => void
}) {
  const titleId = useId()
  const thirdParty = useQuery({
    queryKey: thirdPartyQueryKey,
    queryFn: ({ signal }) => thirdPartyAllowed(signal),
  })
  const changes = usePluginChanges()
  const allowed = thirdParty.data ?? false
  return (
    <section aria-labelledby={titleId}>
      <div className="flex items-start justify-between gap-8">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 id={titleId} className="text-sm font-medium">
            {intl.formatMessage({
              id: "plugins_registry_title",
              defaultMessage: "Third-party",
            })}
          </h3>
          {allowed ? null : (
            <p className="text-sm text-pretty text-muted-foreground">
              {intl.formatMessage({
                id: "plugins_third_party_body",
                defaultMessage:
                  "Plugins from other publishers, and servers you add by URL. Off until you allow them.",
              })}
            </p>
          )}
        </div>
        <ThirdPartySwitch
          allowed={allowed}
          onChange={(next) => changes.thirdParty.mutate(next)}
        />
      </div>
      <RegistryPlugins allowed={allowed} onOpen={onOpen} />
    </section>
  )
}
