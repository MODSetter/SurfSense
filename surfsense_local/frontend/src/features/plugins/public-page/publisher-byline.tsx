import { intl } from "@/i18n/intl"

import { pluginTypeLabel } from "../yours/plugin-type-label"
import { isRegistryEntry, type ListedEntry } from "./listed-entry"

/** Who publishes a listed plugin: SurfSense, or its author, a company or project. Verified or Community sits by its name. */
export function PublisherByline({ entry }: { entry: ListedEntry }) {
  return (
    <span className="truncate">
      {isRegistryEntry(entry)
        ? intl.formatMessage(
            {
              id: "plugins_registry_author_label",
              defaultMessage: "By {author}",
            },
            { author: entry.author }
          )
        : pluginTypeLabel("first_party")}
    </span>
  )
}
