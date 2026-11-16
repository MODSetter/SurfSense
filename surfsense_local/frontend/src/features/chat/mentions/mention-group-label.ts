import { intl } from "@/i18n/intl"

export function mentionGroupLabel(group: string) {
  return group === "artifact"
    ? intl.formatMessage({
        id: "chat_mentions_artifacts_label",
        defaultMessage: "Artifacts",
      })
    : intl.formatMessage({
        id: "chat_mentions_sources_label",
        defaultMessage: "Sources",
      })
}
