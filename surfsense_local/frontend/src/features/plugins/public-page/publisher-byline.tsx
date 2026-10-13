import { Badge } from "@/components/ui/badge"
import { CheckIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { pluginTypeLabel } from "../yours/plugin-type-label"
import { isRegistryEntry, type ListedEntry } from "./listed-entry"

/** Who publishes a listed plugin: SurfSense, a verified partner, or a community author. */
export function PublisherByline({ entry }: { entry: ListedEntry }) {
  if (!isRegistryEntry(entry)) {
    return <span className="truncate">{pluginTypeLabel("first_party")}</span>
  }
  if (entry.verified) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="truncate">{entry.author}</span>
        <Badge variant="secondary">
          <CheckIcon data-icon="inline-start" />
          {intl.formatMessage({
            id: "plugins_registry_verified_label",
            defaultMessage: "Verified",
          })}
        </Badge>
      </span>
    )
  }
  return (
    <span className="truncate">
      {intl.formatMessage(
        { id: "plugins_registry_author_label", defaultMessage: "By {author}" },
        { author: entry.author }
      )}
    </span>
  )
}
