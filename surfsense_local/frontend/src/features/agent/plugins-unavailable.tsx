import { CircleAlertIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { UnavailablePlugin } from "./api"

function label({ title, reason }: UnavailablePlugin) {
  if (reason === "license")
    return intl.formatMessage(
      {
        id: "agent_plugin_license_label",
        defaultMessage: "{plugin} needs a SurfSense license",
      },
      { plugin: title }
    )
  if (reason === "needs_scopes")
    return intl.formatMessage(
      {
        id: "agent_plugin_needs_scopes_label",
        defaultMessage: "{plugin} needs more access",
      },
      { plugin: title }
    )
  return reason === "sign_in"
    ? intl.formatMessage(
        {
          id: "agent_plugin_sign_in_label",
          defaultMessage: "Sign in to {plugin} again",
        },
        { plugin: title }
      )
    : intl.formatMessage(
        {
          id: "agent_plugin_unreachable_label",
          defaultMessage: "Couldn’t reach {plugin}",
        },
        { plugin: title }
      )
}

/** Connected plugins a turn went on without, so their missing tools are explained. */
export function PluginsUnavailable({
  plugins,
}: {
  plugins: UnavailablePlugin[] | null
}) {
  if (!plugins?.length) return null
  return (
    <ul className="mb-2 flex flex-col gap-0.5">
      {plugins.map((plugin) => (
        <li
          key={plugin.title}
          className="flex items-start gap-1.5 text-xs leading-5 text-muted-foreground"
        >
          <CircleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
          <span className="min-w-0 wrap-break-word">{label(plugin)}</span>
        </li>
      ))}
    </ul>
  )
}
