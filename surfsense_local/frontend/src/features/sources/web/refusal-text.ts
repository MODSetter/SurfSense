import { intl } from "@/i18n/intl"

/** Why a pasted line opened no row: it holds no link. */
export function notALinkText(): string {
  return intl.formatMessage({
    id: "sources_web_not_a_link_body",
    defaultMessage: "Not a web link.",
  })
}
