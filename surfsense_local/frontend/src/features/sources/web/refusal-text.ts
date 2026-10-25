import { intl } from "@/i18n/intl"

/** Why a row has no Add: a short link the app won't follow, or text that is no link. */
export function refusalText(refusal: "short_link" | "not_a_link"): string {
  if (refusal === "short_link") {
    return intl.formatMessage({
      id: "sources_web_short_link_body",
      defaultMessage: "A short link. Open it and copy the full link instead.",
    })
  }
  return intl.formatMessage({
    id: "sources_web_not_a_link_body",
    defaultMessage: "Not a web link.",
  })
}
