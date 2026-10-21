import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"

/** Why a plugin waits for Connect, said beside it so the user knows what Connect will ask.
 * None when nothing went wrong: disconnected by the user, or never connected yet. */
export function connectReason(plugin: Plugin): string | null {
  if (plugin.disconnected || plugin.check_failure !== "sign_in") return null
  if (plugin.needs_own_app) {
    return intl.formatMessage({
      id: "plugins_list_reason_needs_own_app_status",
      defaultMessage: "Needs an OAuth app",
    })
  }
  if (plugin.never_signed_in) return null
  if (plugin.needs_scopes.length) {
    return intl.formatMessage({
      id: "plugins_list_reason_needs_scopes_status",
      defaultMessage: "Needs more access",
    })
  }
  if (plugin.auth_type === "oauth") {
    return intl.formatMessage({
      id: "plugins_list_reason_sign_in_expired_status",
      defaultMessage: "Sign-in expired",
    })
  }
  return intl.formatMessage({
    id: "plugins_list_reason_key_refused_status",
    defaultMessage: "Key refused",
  })
}
