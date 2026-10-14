import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"

/** Who publishes the plugin, as the list of connected plugins names it. */
export function pluginTypeLabel(source: Plugin["source"]): string {
  switch (source) {
    case "first_party":
      return intl.formatMessage({
        id: "plugins_list_first_party_label",
        defaultMessage: "By SurfSense",
      })
    case "registry":
      return intl.formatMessage({
        id: "plugins_list_third_party_label",
        defaultMessage: "Third-party",
      })
    case "custom":
      return intl.formatMessage({
        id: "plugins_list_custom_label",
        defaultMessage: "Custom",
      })
  }
}
