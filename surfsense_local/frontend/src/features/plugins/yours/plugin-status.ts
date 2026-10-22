import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"
import { thirdPartyHeld } from "../third-party-held"
import { checkTone, type StatusTone } from "./status-tone"

export type PluginStatus = {
  label: string
  tone: StatusTone
  /** Something new beside the state, not a state of its own. */
  badge?: string
}

/** One short state per plugin: what needs fixing first, then what keeps it unused, then On. */
export function pluginStatus(
  plugin: Plugin,
  thirdPartyAllowed: boolean
): PluginStatus {
  // Red when something broke, amber when it needs a step from the user.
  const failure = (label: string): PluginStatus => ({
    label,
    tone: checkTone(plugin),
  })
  // Before anything else: nothing about it can be acted on until the switch is on.
  if (thirdPartyHeld(plugin, thirdPartyAllowed)) {
    return {
      label: intl.formatMessage({
        id: "plugins_list_third_party_off_status",
        defaultMessage: "Third-party plugins are off",
      }),
      tone: "idle",
    }
  }
  if (plugin.disconnected) {
    return {
      label: intl.formatMessage({
        id: "plugins_list_disconnected_status",
        defaultMessage: "Disconnected",
      }),
      tone: "idle",
    }
  }
  // Nothing else about it matters: no engine can reach it until it is added again by
  // its Streamable HTTP address.
  if (plugin.transport === "sse") {
    return {
      label: intl.formatMessage({
        id: "plugins_list_sse_status",
        defaultMessage: "SSE not supported",
      }),
      tone: "failure",
    }
  }
  if (plugin.removed_reason) {
    // Nothing broke: whether to keep it is the user's call.
    return {
      label: intl.formatMessage({
        id: "plugins_list_removed_status",
        defaultMessage: "No longer listed",
      }),
      tone: "warning",
    }
  }
  switch (plugin.check_failure) {
    case "unreachable":
      return failure(
        intl.formatMessage({
          id: "plugins_list_unreachable_status",
          defaultMessage: "Couldn’t connect",
        })
      )
    case "sign_in":
      return failure(
        plugin.needs_own_app
          ? intl.formatMessage({
              id: "plugins_list_needs_own_app_status",
              defaultMessage: "Needs an OAuth app",
            })
          : plugin.never_signed_in
            ? intl.formatMessage({
                id: "plugins_list_not_connected_status",
                defaultMessage: "Not connected",
              })
            : plugin.needs_scopes.length
              ? intl.formatMessage({
                  id: "plugins_list_needs_scopes_status",
                  defaultMessage: "Needs more access",
                })
              : plugin.auth_type === "oauth"
                ? intl.formatMessage({
                    id: "plugins_list_needs_sign_in_status",
                    defaultMessage: "Needs sign-in",
                  })
                : intl.formatMessage({
                    id: "plugins_list_sign_in_status",
                    defaultMessage: "Needs a new key",
                  })
      )
    case "needs_license":
      return failure(
        intl.formatMessage({
          id: "plugins_list_needs_license_status",
          defaultMessage: "Needs a license",
        })
      )
    case "license_expired":
      return failure(
        intl.formatMessage({
          id: "plugins_list_license_expired_status",
          defaultMessage: "License expired",
        })
      )
    case "license_revoked":
      return failure(
        intl.formatMessage({
          id: "plugins_list_license_revoked_status",
          defaultMessage: "License revoked",
        })
      )
    case "license_invalid":
      return failure(
        intl.formatMessage({
          id: "plugins_list_license_invalid_status",
          defaultMessage: "License not recognized",
        })
      )
    case null:
      break
  }
  if (!plugin.enabled) {
    return {
      label: intl.formatMessage({
        id: "plugins_list_paused_status",
        defaultMessage: "Off",
      }),
      tone: "idle",
    }
  }
  return {
    label: intl.formatMessage({
      id: "plugins_list_on_status",
      defaultMessage: "On",
    }),
    tone: "ok",
    badge: plugin.tools.some((tool) => tool.change)
      ? intl.formatMessage({
          id: "plugins_list_new_tools_status",
          defaultMessage: "New tools",
        })
      : undefined,
  }
}
