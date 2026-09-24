import { Button } from "@/components/ui/button"
import { ServerIcon } from "@/components/ui/icons"
import type { Connection } from "@/features/models/remote/connections/api"
import { intl } from "@/i18n/intl"

/**
 * The other way in, kept to one line under the local list. Servers connected
 * earlier, even on the step before, are named so they are reused, not re-added.
 */
export function ServerOption({
  connections,
  onOpen,
}: {
  connections: Connection[]
  onOpen: () => void
}) {
  const connected = connections.map((connection) => connection.label)
  return (
    <section
      aria-label={intl.formatMessage({ id: "onboarding_server_option_aria" })}
      className="flex items-center justify-between gap-4 pb-1"
    >
      <div className="min-w-0">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <ServerIcon
            aria-hidden="true"
            className="size-4 text-muted-foreground"
          />
          {intl.formatMessage({ id: "onboarding_server_option_title" })}
        </h3>
        {/* pl-6: the icon's 16px plus the 8px gap, so it lines up with the heading text. */}
        <p className="truncate pl-6 text-xs text-muted-foreground">
          {connected.length
            ? intl.formatMessage(
                { id: "onboarding_server_option_connected_body" },
                {
                  servers: intl.formatList(connected, {
                    type: "unit",
                    style: "short",
                  }),
                }
              )
            : intl.formatMessage({ id: "onboarding_server_option_body" })}
        </p>
      </div>
      <Button type="button" variant="outline" onClick={onOpen}>
        {connected.length
          ? intl.formatMessage({ id: "onboarding_server_option_show_button" })
          : intl.formatMessage({
              id: "onboarding_server_option_connect_button",
            })}
      </Button>
    </section>
  )
}
